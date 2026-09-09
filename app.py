import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import io
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="US Stock Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CONSTANTS
# ============================================================

SETTINGS_FILE = "scanner_settings.csv"

DEFAULT_SETTINGS = {
    "min_price": 1.0,
    "max_price": 20.0,
    "min_volume": 100000,
    "min_rvol": 2.0,
    "min_change": 2.0,
    "max_stocks": 300,
    "repeat_tolerance": 0.90,
    "refresh_seconds": 60,
    "auto_scan": True,
}


# ============================================================
# SESSION STATE
# ============================================================

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "NASDAQ:AAPL"

if "scanner_data" not in st.session_state:
    st.session_state.scanner_data = pd.DataFrame()

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None

if "manual_scan_requested" not in st.session_state:
    st.session_state.manual_scan_requested = False


# ============================================================
# SETTINGS
# ============================================================

def load_settings():
    settings = DEFAULT_SETTINGS.copy()

    try:
        if os.path.exists(SETTINGS_FILE):
            df = pd.read_csv(SETTINGS_FILE)

            if not df.empty:
                for _, row in df.iterrows():
                    key = row["setting"]
                    value = row["value"]

                    if key in settings:
                        default_value = settings[key]

                        if isinstance(default_value, bool):
                            settings[key] = str(value).lower() == "true"
                        elif isinstance(default_value, int):
                            settings[key] = int(float(value))
                        else:
                            settings[key] = float(value)

    except Exception:
        pass

    return settings


def save_settings(settings):
    rows = []

    for key, value in settings.items():
        rows.append({
            "setting": key,
            "value": value
        })

    pd.DataFrame(rows).to_csv(SETTINGS_FILE, index=False)


settings = load_settings()


# ============================================================
# MARKET HOURS
# ============================================================

def market_is_open():
    """
    US regular market hours:
    9:30 AM - 4:00 PM Eastern
    Monday-Friday
    """

    eastern = ZoneInfo("America/New_York")
    now = datetime.now(eastern)

    if now.weekday() >= 5:
        return False

    current_time = now.time()

    return time(9, 30) <= current_time <= time(16, 0)


# ============================================================
# RUSSELL 2000
# ============================================================

@st.cache_data(ttl=3600)
def load_russell_2000():

    url = (
        "https://www.ishares.com/us/products/239710/"
        "ishares-russell-2000-etf/latest-holdings.csv"
    )

    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    text = response.text

    # Find the actual CSV header.
    lines = text.splitlines()

    header_index = None

    for i, line in enumerate(lines):
        if line.startswith("Ticker,Name"):
            header_index = i
            break

    if header_index is None:
        raise ValueError("Could not find Russell 2000 holdings header.")

    csv_text = "\n".join(lines[header_index:])

    df = pd.read_csv(io.StringIO(csv_text))

    # Keep equities only.
    if "Asset Class" in df.columns:
        df = df[
            df["Asset Class"]
            .astype(str)
            .str.contains("Equity", case=False, na=False)
        ]

    # Keep US companies.
    if "Location" in df.columns:
        df = df[
            df["Location"]
            .astype(str)
            .str.contains("United States", case=False, na=False)
        ]

    df["Ticker"] = (
        df["Ticker"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    # Yahoo Finance uses "-" instead of "." for some tickers.
    df["YahooTicker"] = df["Ticker"].str.replace(".", "-", regex=False)

    # Remove invalid tickers.
    df = df[
        df["YahooTicker"].notna()
        & (df["YahooTicker"] != "")
        & (df["YahooTicker"] != "NAN")
    ]

    df = df.drop_duplicates("YahooTicker")

    # Exchange map.
    exchange_map = {}

    for ticker in df["Ticker"]:
        # Default to NASDAQ.
        exchange_map[ticker] = "NASDAQ"

    return df.reset_index(drop=True), exchange_map


# ============================================================
# YAHOO DATA HELPERS
# ============================================================

def get_symbol_data(data, symbol):

    try:

        if data is None or data.empty:
            return None

        # MultiIndex columns.
        if isinstance(data.columns, pd.MultiIndex):

            # Case 1: ticker is first level.
            if symbol in data.columns.get_level_values(0):
                result = data[symbol].copy()

            # Case 2: ticker is second level.
            elif symbol in data.columns.get_level_values(1):
                result = data.xs(symbol, axis=1, level=1).copy()

            else:
                return None

        else:
            result = data.copy()

        result = result.dropna(how="all")

        if result.empty:
            return None

        return result

    except Exception:
        return None


# ============================================================
# 1-MINUTE REPEAT DETECTION
# ============================================================

def detect_repeat(session_data, tolerance=0.90):

    if session_data is None or session_data.empty:
        return False, 0, 0

    try:

        volume = pd.to_numeric(
            session_data["Volume"],
            errors="coerce"
        ).fillna(0)

        volume = volume[volume > 0]

        if len(volume) < 2:
            return False, 0, 0

        current_volume = float(volume.iloc[-1])

        previous_volumes = volume.iloc[:-1]

        if previous_volumes.empty:
            return False, current_volume, 0

        previous_spike = float(previous_volumes.max())

        if previous_spike <= 0:
            return False, current_volume, previous_spike

        repeat = current_volume >= (
            previous_spike * tolerance
        )

        return (
            bool(repeat),
            current_volume,
            previous_spike
        )

    except Exception:
        return False, 0, 0


# ============================================================
# SCAN ONE BATCH
# ============================================================

def scan_batch(symbols):

    results = []

    if not symbols:
        return results

    # --------------------------------------------------------
    # 1-MINUTE DATA
    # --------------------------------------------------------

    try:

        intraday = yf.download(
            tickers=symbols,
            period="1d",
            interval="1m",
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            threads=True,
            progress=False
        )

    except Exception:
        intraday = None

    # --------------------------------------------------------
    # DAILY DATA FOR RELATIVE VOLUME
    # --------------------------------------------------------

    try:

        daily = yf.download(
            tickers=symbols,
            period="20d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            threads=True,
            progress=False
        )

    except Exception:
        daily = None

    # --------------------------------------------------------
    # PROCESS EACH STOCK
    # --------------------------------------------------------

    for symbol in symbols:

        try:

            intraday_symbol = get_symbol_data(
                intraday,
                symbol
            )

            if intraday_symbol is None:
                continue

            if "Close" not in intraday_symbol.columns:
                continue

            if "Volume" not in intraday_symbol.columns:
                continue

            intraday_symbol = intraday_symbol.dropna(
                subset=["Close"]
            )

            if intraday_symbol.empty:
                continue

            # ------------------------------------------------
            # Latest price
            # ------------------------------------------------

            ltp = float(
                intraday_symbol["Close"].iloc[-1]
            )

            if ltp <= 0:
                continue

            # ------------------------------------------------
            # Session volume
            # ------------------------------------------------

            session_volume = float(
                pd.to_numeric(
                    intraday_symbol["Volume"],
                    errors="coerce"
                )
                .fillna(0)
                .sum()
            )

            # ------------------------------------------------
            # Current 1-minute volume
            # ------------------------------------------------

            current_minute_volume = float(
                pd.to_numeric(
                    intraday_symbol["Volume"],
                    errors="coerce"
                )
                .fillna(0)
                .iloc[-1]
            )

            # ------------------------------------------------
            # Repeat detection
            # ------------------------------------------------

            repeat, current_volume, previous_spike = (
                detect_repeat(
                    intraday_symbol,
                    settings["repeat_tolerance"]
                )
            )

            # ------------------------------------------------
            # Previous closing price
            # ------------------------------------------------

            daily_symbol = get_symbol_data(
                daily,
                symbol
            )

            previous_close = None

            if (
                daily_symbol is not None
                and "Close" in daily_symbol.columns
            ):

                closes = pd.to_numeric(
                    daily_symbol["Close"],
                    errors="coerce"
                ).dropna()

                if len(closes) >= 2:
                    previous_close = float(
                        closes.iloc[-2]
                    )

            # ------------------------------------------------
            # Percentage change
            # ------------------------------------------------

            if previous_close and previous_close > 0:

                pct_change = (
                    (ltp - previous_close)
                    / previous_close
                    * 100
                )

            else:
                pct_change = 0.0

            # ------------------------------------------------
            # Basic Relative Volume
            #
            # Session volume compared with average
            # previous 5 trading days.
            # ------------------------------------------------

            rvol = 0.0

            if (
                daily_symbol is not None
                and "Volume" in daily_symbol.columns
            ):

                daily_volume = pd.to_numeric(
                    daily_symbol["Volume"],
                    errors="coerce"
                ).dropna()

                if len(daily_volume) >= 2:

                    previous_days = daily_volume.iloc[:-1]

                    previous_days = previous_days.tail(5)

                    average_previous_volume = (
                        previous_days.mean()
                    )

                    if (
                        average_previous_volume > 0
                        and session_volume > 0
                    ):

                        rvol = (
                            session_volume
                            / average_previous_volume
                        )

            # ------------------------------------------------
            # Timestamp
            # ------------------------------------------------

            timestamp = intraday_symbol.index[-1]

            try:
                timestamp = pd.to_datetime(timestamp)

                if timestamp.tzinfo is not None:
                    timestamp = timestamp.tz_convert(
                        "America/New_York"
                    )

                timestamp_string = timestamp.strftime(
                    "%H:%M"
                )

            except Exception:
                timestamp_string = ""

            # ------------------------------------------------
            # Result
            # ------------------------------------------------

            results.append({
                "Time": timestamp_string,
                "Symbol": symbol,
                "LTP": ltp,
                "% Change": pct_change,
                "Rel Vol": rvol,
                "Repeat": "🔁" if repeat else "",
                "_Repeat": repeat,
                "_CurrentMinuteVolume": current_volume,
                "_PreviousSpike": previous_spike,
                "_SessionVolume": session_volume
            })

        except Exception:
            continue

    return results


# ============================================================
# MAIN SCANNER
# ============================================================

def run_scanner():

    try:

        russell_df, exchange_map = load_russell_2000()

        max_stocks = int(
            settings["max_stocks"]
        )

        symbols = (
            russell_df["YahooTicker"]
            .head(max_stocks)
            .tolist()
        )

        all_results = []

        # Scan in batches to reduce Yahoo requests.
        batch_size = 50

        for i in range(
            0,
            len(symbols),
            batch_size
        ):

            batch = symbols[
                i:i + batch_size
            ]

            batch_results = scan_batch(batch)

            all_results.extend(
                batch_results
            )

        if not all_results:
            return pd.DataFrame()

        df = pd.DataFrame(all_results)

        # ----------------------------------------------------
        # Filters
        # ----------------------------------------------------

        df = df[
            (df["LTP"] >= settings["min_price"])
            & (df["LTP"] <= settings["max_price"])
            & (
                df["_SessionVolume"]
                >= settings["min_volume"]
            )
            & (
                df["Rel Vol"]
                >= settings["min_rvol"]
            )
            & (
                df["% Change"]
                >= settings["min_change"]
            )
        ]

        # ----------------------------------------------------
        # Sort:
        # Repeat stocks first, then Rel Vol.
        # ----------------------------------------------------

        if not df.empty:

            df = df.sort_values(
                by=[
                    "_Repeat",
                    "Rel Vol",
                    "% Change"
                ],
                ascending=[
                    False,
                    False,
                    False
                ]
            )

        # Keep only display columns.
        display_columns = [
            "Time",
            "Symbol",
            "LTP",
            "% Change",
            "Rel Vol",
            "Repeat"
        ]

        for col in display_columns:

            if col not in df.columns:
                df[col] = ""

        return df[
            display_columns
        ].reset_index(drop=True)

    except Exception as e:

        st.error(
            f"Scanner error: {e}"
        )

        return pd.DataFrame()


# ============================================================
# TRADINGVIEW CHART
# ============================================================

def show_tradingview(ticker):

    if not ticker:
        return

    # Remove existing exchange if supplied.
    clean_ticker = ticker.split(":")[-1]

    # Determine exchange.
    exchange = "NASDAQ"

    try:

        russell_df, exchange_map = load_russell_2000()

        original_ticker = clean_ticker.replace(
            "-",
            "."
        )

        exchange = exchange_map.get(
            original_ticker,
            "NASDAQ"
        )

    except Exception:
        exchange = "NASDAQ"

    tradingview_symbol = (
        f"{exchange}:{clean_ticker}"
    )

    # TradingView widget.
    chart_html = f"""
    <div class="tradingview-widget-container"
         style="height:560px;width:100%;">

      <div id="tradingview_chart"
           style="height:560px;width:100%;"></div>

      <script type="text/javascript"
              src="https://s3.tradingview.com/tv.js">
      </script>

      <script type="text/javascript">

      new TradingView.widget({{
          "autosize": true,
          "symbol": "{tradingview_symbol}",
          "interval": "1",
          "timezone": "America/New_York",
          "theme": "dark",
          "style": "1",
          "locale": "en",
          "enable_publishing": false,
          "hide_top_toolbar": false,
          "hide_side_toolbar": false,
          "allow_symbol_change": true,
          "save_image": false,
          "container_id": "tradingview_chart"
      }});

      </script>
    </div>
    """

    st.components.v1.html(
        chart_html,
        height=570
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("⚙️ Scanner Settings")

    st.subheader("Automatic Scanner")

    auto_scan = st.toggle(
        "Auto Scanner",
        value=settings["auto_scan"]
    )

    refresh_options = [
        30,
        60,
        90,
        120,
        180,
        300
    ]

    current_refresh = int(
        settings["refresh_seconds"]
    )

    if current_refresh not in refresh_options:
        current_refresh = 60

    refresh_seconds = st.selectbox(
        "Refresh every",
        refresh_options,
        index=refresh_options.index(
            current_refresh
        ),
        format_func=lambda x: f"{x} seconds"
    )

    st.divider()

    st.subheader("Universe")

    max_stocks = st.number_input(
        "Maximum Russell 2000 stocks",
        min_value=50,
        max_value=1958,
        value=int(settings["max_stocks"]),
        step=50
    )

    st.caption(
        "Higher numbers scan more Russell 2000 stocks "
        "but require more Yahoo Finance requests."
    )

    st.divider()

    st.subheader("Price")

    min_price = st.number_input(
        "Minimum price",
        min_value=0.01,
        value=float(settings["min_price"]),
        step=0.50
    )

    max_price = st.number_input(
        "Maximum price",
        min_value=0.01,
        value=float(settings["max_price"]),
        step=1.00
    )

    st.divider()

    st.subheader("Volume")

    min_volume = st.number_input(
        "Minimum volume",
        min_value=0,
        value=int(settings["min_volume"]),
        step=10000
    )

    st.divider()

    st.subheader("Momentum")

    min_rvol = st.number_input(
        "Minimum Rel Vol",
        min_value=0.0,
        value=float(settings["min_rvol"]),
        step=0.5
    )

    min_change = st.number_input(
        "Minimum % Change",
        min_value=-100.0,
        max_value=1000.0,
        value=float(settings["min_change"]),
        step=0.5
    )

    st.divider()

    st.subheader("🔁 Repeat Detection")

    repeat_percentage = st.slider(
        "Repeat threshold",
        min_value=50,
        max_value=100,
        value=int(
            settings["repeat_tolerance"] * 100
        ),
        step=5
    )

    st.caption(
        "Example: 90% means the current 1-minute "
        "volume must reach at least 90% of the "
        "previous highest 1-minute volume."
    )

    st.divider()

    save_button = st.button(
        "💾 Save Settings",
        use_container_width=True
    )

    scan_button = st.button(
        "🔍 Scan Now",
        use_container_width=True
    )


# ============================================================
# APPLY SIDEBAR SETTINGS
# ============================================================

settings["auto_scan"] = auto_scan
settings["refresh_seconds"] = refresh_seconds
settings["max_stocks"] = max_stocks
settings["min_price"] = min_price
settings["max_price"] = max_price
settings["min_volume"] = min_volume
settings["min_rvol"] = min_rvol
settings["min_change"] = min_change
settings["repeat_tolerance"] = (
    repeat_percentage / 100
)


if save_button:

    save_settings(settings)

    st.sidebar.success(
        "Settings saved."
    )


if scan_button:

    st.session_state.manual_scan_requested = True


# ============================================================
# TITLE
# ============================================================

st.title("📈 US Stock Momentum Scanner")

st.caption(
    "Russell 2000 • 1-Minute Momentum • "
    "Relative Volume • Repeat Volume Signals"
)


# ============================================================
# AUTOMATIC SCANNER
# ============================================================

run_every = None

if (
    auto_scan
    and market_is_open()
):
    run_every = f"{refresh_seconds}s"


@st.fragment(run_every=run_every)
def automatic_scanner():

    should_scan = False

    # Automatic scan during market hours.
    if auto_scan and market_is_open():
        should_scan = True

    # Manual scan.
    if st.session_state.manual_scan_requested:
        should_scan = True
        st.session_state.manual_scan_requested = False

    # First load.
    if (
        st.session_state.scanner_data.empty
        and not auto_scan
    ):
        should_scan = True

    # --------------------------------------------------------
    # Run scanner
    # --------------------------------------------------------

    if should_scan:

        with st.spinner(
            "Scanning Russell 2000..."
        ):

            data = run_scanner()

        st.session_state.scanner_data = data

        eastern = ZoneInfo(
            "America/New_York"
        )

        st.session_state.last_scan = (
            datetime.now(eastern)
        )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    if market_is_open():

        if auto_scan:

            st.success(
                f"🟢 Auto scanner running — "
                f"1-minute candles — "
                f"refresh every {refresh_seconds}s"
            )

        else:

            st.info(
                "🟡 Market open — Auto Scanner is OFF"
            )

    else:

        st.warning(
            "🔴 US regular market is currently closed."
        )

    if st.session_state.last_scan:

        scan_time = (
            st.session_state.last_scan
            .strftime("%H:%M:%S")
        )

        st.caption(
            f"Last scan: {scan_time} "
            f"US Eastern Time"
        )

    # ========================================================
    # TWO COLUMN LAYOUT
    # ========================================================

    scanner_col, chart_col = st.columns(
        [35, 65],
        gap="small"
    )

    # ========================================================
    # SCANNER
    # ========================================================

    with scanner_col:

        st.subheader("Scanner")

        data = st.session_state.scanner_data

        if data.empty:

            st.info(
                "No stocks currently match your filters."
            )

        else:

            st.caption(
                f"{len(data)} stocks found"
            )

            # ------------------------------------------------
            # Table header
            # ------------------------------------------------

            header_cols = st.columns(
                [0.8, 1.1, 1.0, 1.0, 1.0, 0.8]
            )

            headers = [
                "Time",
                "Symbol",
                "LTP",
                "% Change",
                "Rel Vol",
                "Repeat"
            ]

            for col, header in zip(
                header_cols,
                headers
            ):

                col.markdown(
                    f"**{header}**"
                )

            st.divider()

            # ------------------------------------------------
            # Rows
            # ------------------------------------------------

            for _, row in data.iterrows():

                row_cols = st.columns(
                    [0.8, 1.1, 1.0, 1.0, 1.0, 0.8]
                )

                row_cols[0].write(
                    row["Time"]
                )

                # Clickable ticker.
                if row_cols[1].button(
                    row["Symbol"],
                    key=(
                        f"ticker_"
                        f"{row['Symbol']}_"
                        f"{row['Time']}"
                    ),
                    use_container_width=True
                ):

                    st.session_state.selected_ticker = (
                        row["Symbol"]
                    )

                    st.rerun()

                row_cols[2].write(
                    f"${row['LTP']:.2f}"
                )

                row_cols[3].write(
                    f"{row['% Change']:.2f}%"
                )

                row_cols[4].write(
                    f"{row['Rel Vol']:.1f}"
                )

                row_cols[5].write(
                    row["Repeat"]
                )

    # ========================================================
    # TRADINGVIEW
    # ========================================================

    with chart_col:

        selected = (
            st.session_state.selected_ticker
        )

        st.subheader(
            f"TradingView — {selected}"
        )

        show_tradingview(
            selected
        )


# ============================================================
# RUN
# ============================================================

automatic_scanner()
