from flask import Flask, render_template, jsonify, request
import yfinance as yf
import pandas as pd
import numpy as np
import threading
import time
from datetime import datetime

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

REFRESH_SECONDS = 60

# Prototype universe.
# We can later replace this with the full US stock universe.
STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "GOOGL",
    "GOOG", "AVGO", "AMD", "NFLX", "PLTR", "MU", "INTC",
    "SMCI", "ARM", "MSTR", "COIN", "HOOD", "SOFI",
    "RIVN", "LCID", "NIO", "XPEV", "LI",
    "BBAI", "SOUN", "AI", "IONQ", "RGTI",
    "RKLB", "ASTS", "LUNR", "OKLO", "SMR",
    "CRWD", "PANW", "NET", "SNOW", "DDOG",
    "SHOP", "UBER", "ABNB", "DASH", "PYPL",
    "JPM", "BAC", "C", "WFC", "GS",
    "XOM", "CVX", "OXY",
    "BA", "GE", "CAT",
    "COST", "WMT", "TGT",
    "NKE", "DIS",
    "PFE", "MRNA",
    "CVNA", "MARA", "RIOT",
    "CLSK", "HUT", "BITF",
    "GME", "AMC",
    "BB", "SNAP", "RBLX",
    "DKNG", "PLTK",
    "TQQQ", "SQQQ", "SOXL", "SOXS",
]

# Cache
scanner_cache = []
last_update = None

# Lock prevents multiple scans at once
scan_lock = threading.Lock()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def calculate_rvol(current_volume, average_volume):
    """
    Simple daily Relative Volume:

        RVOL = today's volume / average 20-day volume

    Example:
        today's volume = 20 million
        average volume = 2 million

        RVOL = 10x
    """

    if average_volume <= 0:
        return 0.0

    return current_volume / average_volume


def calculate_volume_spike(symbol):
    """
    Prototype volume spike calculation.

    Downloads recent 5-minute data and compares the latest
    completed bar with the average of recent bars.

    This is NOT a production-grade institutional volume model.
    It is intended for the prototype.
    """

    try:
        data = yf.download(
            symbol,
            period="5d",
            interval="5m",
            progress=False,
            auto_adjust=False,
            threads=False
        )

        if data.empty:
            return 0.0, False

        # Handle MultiIndex columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        if "Volume" not in data.columns:
            return 0.0, False

        volume = data["Volume"].dropna()

        if len(volume) < 25:
            return 0.0, False

        latest_volume = float(volume.iloc[-1])

        previous_volume = volume.iloc[-21:-1]

        average_previous = previous_volume.mean()

        if average_previous <= 0:
            return 0.0, False

        spike_ratio = latest_volume / average_previous

        return float(spike_ratio), spike_ratio >= 3.0

    except Exception:
        return 0.0, False


def get_stock_data(symbol):
    """
    Get daily stock information.
    """

    try:
        ticker = yf.Ticker(symbol)

        hist = ticker.history(
            period="3mo",
            interval="1d",
            auto_adjust=False
        )

        if hist.empty:
            return None

        hist = hist.dropna(subset=["Close", "Volume"])

        if len(hist) < 20:
            return None

        current = hist.iloc[-1]

        current_price = safe_float(current["Close"])
        current_volume = safe_float(current["Volume"])

        previous_close = safe_float(
            hist.iloc[-2]["Close"]
        )

        if previous_close > 0:
            change_percent = (
                (current_price - previous_close)
                / previous_close
            ) * 100
        else:
            change_percent = 0

        # Average 20-day volume excluding today
        previous_20_volume = hist["Volume"].iloc[-21:-1]

        average_volume = safe_float(
            previous_20_volume.mean()
        )

        rvol = calculate_rvol(
            current_volume,
            average_volume
        )

        # 20-day high
        high_20 = safe_float(
            hist["High"].iloc[-21:].max()
        )

        distance_from_20_high = 0

        if high_20 > 0:
            distance_from_20_high = (
                (current_price / high_20) - 1
            ) * 100

        # 52-week high
        high_52 = safe_float(
            hist["High"].max()
        )

        distance_from_52_high = 0

        if high_52 > 0:
            distance_from_52_high = (
                (current_price / high_52) - 1
            ) * 100

        # Volume spike
        volume_spike, spike_detected = calculate_volume_spike(
            symbol
        )

        # Momentum score
        score = 0

        if change_percent >= 2:
            score += 2

        if change_percent >= 5:
            score += 2

        if rvol >= 2:
            score += 2

        if rvol >= 5:
            score += 2

        if rvol >= 10:
            score += 3

        if volume_spike >= 3:
            score += 2

        if volume_spike >= 5:
            score += 3

        return {
            "symbol": symbol,
            "name": symbol,
            "price": round(current_price, 2),
            "volume": int(current_volume),
            "average_volume": int(average_volume),
            "rvol": round(rvol, 2),
            "change_percent": round(change_percent, 2),
            "volume_spike": round(volume_spike, 2),
            "spike_detected": spike_detected,
            "high_20": round(high_20, 2),
            "distance_20_high": round(
                distance_from_20_high,
                2
            ),
            "high_52": round(high_52, 2),
            "distance_52_high": round(
                distance_from_52_high,
                2
            ),
            "score": score,
        }

    except Exception as e:
        print(f"Error {symbol}: {e}")
        return None


# ============================================================
# SCANNER
# ============================================================

def run_scanner():
    global scanner_cache
    global last_update

    if scan_lock.locked():
        return

    with scan_lock:

        print("\n==============================")
        print("Starting stock scan...")
        print("==============================")

        results = []

        # Download daily data in one batch.
        # This is much faster than individually requesting
        # every stock.
        try:

            data = yf.download(
                STOCKS,
                period="3mo",
                interval="1d",
                progress=False,
                auto_adjust=False,
                group_by="ticker",
                threads=True
            )

        except Exception as e:

            print("Download error:", e)
            return

        if data.empty:
            print("No market data received.")
            return

        for symbol in STOCKS:

            try:

                if isinstance(data.columns, pd.MultiIndex):

                    if symbol not in data.columns.get_level_values(0):
                        continue

                    hist = data[symbol].copy()

                else:

                    hist = data.copy()

                hist = hist.dropna(
                    subset=["Close", "Volume"]
                )

                if len(hist) < 20:
                    continue

                current = hist.iloc[-1]

                price = safe_float(current["Close"])
                volume = safe_float(current["Volume"])

                previous_close = safe_float(
                    hist.iloc[-2]["Close"]
                )

                if previous_close <= 0:
                    continue

                change = (
                    (price - previous_close)
                    / previous_close
                ) * 100

                avg_volume = safe_float(
                    hist["Volume"]
                    .iloc[-21:-1]
                    .mean()
                )

                rvol = calculate_rvol(
                    volume,
                    avg_volume
                )

                high_20 = safe_float(
                    hist["High"].iloc[-21:].max()
                )

                high_52 = safe_float(
                    hist["High"].max()
                )

                distance_20 = (
                    ((price / high_20) - 1) * 100
                    if high_20 > 0 else 0
                )

                distance_52 = (
                    ((price / high_52) - 1) * 100
                    if high_52 > 0 else 0
                )

                # Initial score
                score = 0

                if change >= 2:
                    score += 2

                if change >= 5:
                    score += 2

                if rvol >= 2:
                    score += 2

                if rvol >= 5:
                    score += 2

                if rvol >= 10:
                    score += 3

                result = {
                    "symbol": symbol,
                    "name": symbol,
                    "price": round(price, 2),
                    "volume": int(volume),
                    "average_volume": int(avg_volume),
                    "rvol": round(rvol, 2),
                    "change_percent": round(change, 2),
                    "volume_spike": 0,
                    "spike_detected": False,
                    "high_20": round(high_20, 2),
                    "distance_20_high": round(
                        distance_20,
                        2
                    ),
                    "high_52": round(high_52, 2),
                    "distance_52_high": round(
                        distance_52,
                        2
                    ),
                    "score": score,
                }

                results.append(result)

            except Exception as e:

                print(
                    f"Processing error {symbol}: {e}"
                )

        # Sort by score first
        results.sort(
            key=lambda x: (
                x["score"],
                x["rvol"],
                x["change_percent"]
            ),
            reverse=True
        )

        scanner_cache = results
        last_update = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        print(
            f"Scan complete: {len(results)} stocks"
        )


# ============================================================
# BACKGROUND REFRESH
# ============================================================

def background_scanner():

    while True:

        try:
            run_scanner()

        except Exception as e:
            print(
                "Background scanner error:",
                e
            )

        time.sleep(REFRESH_SECONDS)


# ============================================================
# WEB ROUTES
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


@app.route("/api/stocks")
def stocks():

    # Read filters from URL
    try:
        min_price = float(
            request.args.get(
                "min_price",
                0
            )
        )
    except:
        min_price = 0

    try:
        max_price = float(
            request.args.get(
                "max_price",
                999999
            )
        )
    except:
        max_price = 999999

    try:
        min_volume = int(
            request.args.get(
                "min_volume",
                100000
            )
        )
    except:
        min_volume = 100000

    try:
        min_change = float(
            request.args.get(
                "min_change",
                0
            )
        )
    except:
        min_change = 0

    try:
        min_rvol = float(
            request.args.get(
                "min_rvol",
                0
            )
        )
    except:
        min_rvol = 0

    search = request.args.get(
        "search",
        ""
    ).strip().upper()

    sort_by = request.args.get(
        "sort",
        "score"
    )

    filtered = []

    for stock in scanner_cache:

        if stock["price"] < min_price:
            continue

        if stock["price"] > max_price:
            continue

        if stock["volume"] < min_volume:
            continue

        if stock["change_percent"] < min_change:
            continue

        if stock["rvol"] < min_rvol:
            continue

        if search:

            if search not in stock["symbol"].upper():

                continue

        filtered.append(stock)

    # Sorting
    if sort_by == "price":

        filtered.sort(
            key=lambda x: x["price"],
            reverse=True
        )

    elif sort_by == "volume":

        filtered.sort(
            key=lambda x: x["volume"],
            reverse=True
        )

    elif sort_by == "change":

        filtered.sort(
            key=lambda x: x["change_percent"],
            reverse=True
        )

    elif sort_by == "rvol":

        filtered.sort(
            key=lambda x: x["rvol"],
            reverse=True
        )

    else:

        filtered.sort(
            key=lambda x: x["score"],
            reverse=True
        )

    return jsonify({
        "updated": last_update,
        "count": len(filtered),
        "stocks": filtered
    })


@app.route("/api/status")
def status():

    return jsonify({
        "updated": last_update,
        "total": len(scanner_cache)
    })


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    # Initial scan
    print("Running initial scanner...")

    run_scanner()

    # Background scanner
    thread = threading.Thread(
        target=background_scanner,
        daemon=True
    )

    thread.start()

    print("")
    print("==============================")
    print("US STOCK SCANNER")
    print("==============================")
    print("Open:")
    print("http://127.0.0.1:5000")
    print("==============================")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False
    )
