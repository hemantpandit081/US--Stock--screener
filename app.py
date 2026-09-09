import streamlit as st
import yfinance as yf
import pandas as pd
import json
import os
import time
import streamlit.components.v1 as components

# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="US Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>

html, body, [class*="css"] {
    font-family: Arial, sans-serif;
}

.stApp {
    background: #0b0f14;
    color: #ffffff;
}

section[data-testid="stSidebar"] {
    background: #11161d;
}

.block-container {
    padding-top: 1rem;
    padding-left: 1rem;
    padding-right: 1rem;
}

h1 {
    font-size: 24px !important;
    margin-bottom: 5px !important;
}

.scanner-header {
    background: #161c24;
    border-bottom: 1px solid #303741;
    padding: 8px 5px;
    color: #9da7b3;
    font-size: 12px;
    font-weight: bold;
}

.stock-row {
    border-bottom: 1px solid #20262e;
    padding: 3px 0px;
}

.metric {
    font-size: 13px;
    color: #e5e7eb;
}

.symbol {
    font-size: 14px;
    font-weight: bold;
}

.green {
    color: #22c55e;
}

.red {
    color: #ef4444;
}

.repeat-dot {
    color: white;
    font-size: 13px;
    margin-left: 4px;
}

.small-text {
    color: #7f8a98;
    font-size: 11px;
}

div.stButton > button {
    background: transparent;
    border: none;
    color: #ffffff;
    padding: 0px;
    margin: 0px;
    font-size: 14px;
    font-weight: bold;
    text-align: left;
}

div.stButton > button:hover {
    color: #38bdf8;
    border: none;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# TITLE
# =========================================================

st.title("📈 US Momentum Scanner")

# =========================================================
# SETTINGS
# =========================================================

DEFAULT_SETTINGS = {
    "min_price": 1.0,
    "max_price": 20.0,
    "min_volume": 100000,
    "min_rvol": 2.0,
    "min_change": 2.0,
    "repeat_tolerance": 90,
    "refresh_seconds": 60,
    "auto_scan": False
}

SETTINGS_FILE = "scanner_settings.json"


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except:
            pass

    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)


settings = load_settings()

# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.header("Scanner Filters")

    auto_scan = st.checkbox(
        "Automatic Scanner",
        value=settings["auto_scan"]
    )

    refresh_seconds = st.number_input(
        "Refresh Seconds",
        min_value=10,
        max_value=600,
        value=int(settings["refresh_seconds"]),
        step=10
    )

    min_price = st.number_input(
        "Minimum Price",
        min_value=0.01,
        value=float(settings["min_price"]),
        step=0.50
    )

    max_price = st.number_input(
        "Maximum Price",
        min_value=0.01,
        value=float(settings["max_price"]),
        step=0.50
    )

    min_volume = st.number_input(
        "Minimum Volume",
        min_value=0,
        value=int(settings["min_volume"]),
        step=10000
    )

    min_rvol = st.number_input(
        "Minimum Relative Volume",
        min_value=0.1,
        value=float(settings["min_rvol"]),
        step=0.5
    )

    min_change = st.number_input(
        "Minimum % Change",
        min_value=0.0,
        value=float(settings["min_change"]),
        step=0.5
    )

    repeat_tolerance = st.number_input(
        "Repeat Volume Tolerance %",
        min_value=50,
        max_value=100,
        value=int(settings["repeat_tolerance"]),
        step=5
    )

    save_button = st.button("Save Settings")

    scan_button = st.button("🔎 Scan Now")

    if save_button:

        settings = {
            "min_price": min_price,
            "max_price": max_price,
            "min_volume": min_volume,
            "min_rvol": min_rvol,
            "min_change": min_change,
            "repeat_tolerance": repeat_tolerance,
            "refresh_seconds": refresh_seconds,
            "auto_scan": auto_scan
        }

        save_settings(settings)

        st.success("Settings saved")

# =========================================================
# LOAD RUSSELL 2000
# =========================================================

@st.cache_data
def load_symbols():

    try:

        df = pd.read_csv("russell2000.csv")

        possible_columns = [
            "Symbol",
            "symbol",
            "Ticker",
            "ticker"
        ]

        symbol_column = None

        for col in possible_columns:
            if col in df.columns:
                symbol_column = col
                break

        if symbol_column is None:
            return []

        symbols = (
            df[symbol_column]
            .dropna()
            .astype(str)
            .str.upper()
            .str.strip()
            .tolist()
        )

        symbols = list(dict.fromkeys(symbols))

        return symbols

    except Exception:

        return []


symbols = load_symbols()

# =========================================================
# SESSION STATE
# =========================================================

if "results" not in st.session_state:
    st.session_state.results = []

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "NVDA"

if "last_scan" not in st.session_state:
    st.session_state.last_scan = 0


# =========================================================
# SCANNER
# =========================================================

def scan_market():

    results = []

    if not symbols:
        return results

    # -----------------------------------------------------
    # Download 1-minute data
    # -----------------------------------------------------

    try:

        intraday = yf.download(
            tickers=symbols,
            period="1d",
            interval="1m",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True
        )

    except Exception:

        return results

    # -----------------------------------------------------
    # Daily data
    # -----------------------------------------------------

    try:

        daily = yf.download(
            tickers=symbols,
            period="20d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True
        )

    except Exception:

        return results

    # -----------------------------------------------------
    # Process stocks
    # -----------------------------------------------------

    for symbol in symbols:

        try:

            # =============================
            # Intraday
            # =============================

            if len(symbols) == 1:

                minute_df = intraday.copy()

            else:

                if symbol not in intraday.columns.get_level_values(0):
                    continue

                minute_df = intraday[symbol].copy()

            minute_df = minute_df.dropna(subset=["Close", "Volume"])

            if minute_df.empty:
                continue

            # =============================
            # Last price
            # =============================

            last_price = float(
                minute_df["Close"].iloc[-1]
            )

            # =============================
            # Current 1 minute volume
            # =============================

            current_volume = float(
                minute_df["Volume"].iloc[-1]
            )

            # =============================
            # Session volume
            # =============================

            session_volume = float(
                minute_df["Volume"].sum()
            )

            # =============================
            # Highest previous 1-min volume
            # =============================

            previous_volumes = minute_df["Volume"].iloc[:-1]

            if len(previous_volumes) > 0:

                previous_high_volume = float(
                    previous_volumes.max()
                )

            else:

                previous_high_volume = 0

            # =============================
            # Repeat volume
            # =============================

            repeat_volume = False

            if previous_high_volume > 0:

                repeat_volume = (
                    current_volume
                    >= previous_high_volume
                    * repeat_tolerance
                    / 100
                )

            # =============================
            # Daily data
            # =============================

            if len(symbols) == 1:

                daily_df = daily.copy()

            else:

                if symbol not in daily.columns.get_level_values(0):
                    continue

                daily_df = daily[symbol].copy()

            daily_df = daily_df.dropna(
                subset=["Close", "Volume"]
            )

            if len(daily_df) < 2:
                continue

            # =============================
            # Previous close
            # =============================

            previous_close = float(
                daily_df["Close"].iloc[-2]
            )

            # =============================
            # Percentage change
            # =============================

            percent_change = (
                (last_price - previous_close)
                / previous_close
            ) * 100

            # =============================
            # Average daily volume
            # =============================

            historical_volume = daily_df["Volume"].iloc[:-1]

            if len(historical_volume) > 5:

                average_volume = float(
                    historical_volume.iloc[-5:].mean()
                )

            else:

                average_volume = float(
                    historical_volume.mean()
                )

            if average_volume <= 0:
                continue

            # =============================
            # Relative Volume
            # =============================

            rvol = (
                session_volume
                / average_volume
            )

            # =============================
            # Filters
            # =============================

            if last_price < min_price:
                continue

            if last_price > max_price:
                continue

            if session_volume < min_volume:
                continue

            if rvol < min_rvol:
                continue

            if percent_change < min_change:
                continue

            # =============================
            # Time
            # =============================

            timestamp = minute_df.index[-1]

            try:
                display_time = timestamp.strftime("%H:%M")
            except:
                display_time = ""

            # =============================
            # Add result
            # =============================

            results.append({

                "time": display_time,

                "symbol": symbol,

                "price": last_price,

                "change": percent_change,

                "rvol": rvol,

                "repeat": repeat_volume,

                "current_volume": current_volume,

                "session_volume": session_volume

            })

        except Exception:
            continue

    # =====================================================
    # SORT
    # =====================================================

    results = sorted(
        results,
        key=lambda x: (
            x["repeat"],
            x["rvol"],
            x["change"]
        ),
        reverse=True
    )

    return results


# =========================================================
# SCAN LOGIC
# =========================================================

should_scan = False

if scan_button:
    should_scan = True

if auto_scan:
    should_scan = True

if not st.session_state.results:
    should_scan = False


if should_scan:

    with st.spinner("Scanning market..."):

        st.session_state.results = scan_market()
        st.session_state.last_scan = time.time()


# =========================================================
# AUTO REFRESH
# =========================================================

if auto_scan:

    time_since_scan = (
        time.time()
        - st.session_state.last_scan
    )

    if time_since_scan >= refresh_seconds:

        st.session_state.results = scan_market()

        st.session_state.last_scan = time.time()

        st.rerun()


# =========================================================
# MAIN LAYOUT
# =========================================================

scanner_col, chart_col = st.columns(
    [35, 65],
    gap="small"
)


# =========================================================
# SCANNER
# =========================================================

with scanner_col:

    st.subheader("Momentum Stocks")

    # Header

    h1, h2, h3, h4, h5 = st.columns(
        [0.65, 1.45, 0.85, 0.95, 0.75],
        gap="small"
    )

    h1.markdown(
        '<div class="scanner-header">Time</div>',
        unsafe_allow_html=True
    )

    h2.markdown(
        '<div class="scanner-header">Symbol</div>',
        unsafe_allow_html=True
    )

    h3.markdown(
        '<div class="scanner-header">LTP</div>',
        unsafe_allow_html=True
    )

    h4.markdown(
        '<div class="scanner-header">% Change</div>',
        unsafe_allow_html=True
    )

    h5.markdown(
        '<div class="scanner-header">Rel Vol</div>',
        unsafe_allow_html=True
    )

    # -----------------------------------------------------
    # Rows
    # -----------------------------------------------------

    for row in st.session_state.results:

        c1, c2, c3, c4, c5 = st.columns(
            [0.65, 1.45, 0.85, 0.95, 0.75],
            gap="small"
        )

        # Time

        c1.markdown(
            f'<span class="small-text">{row["time"]}</span>',
            unsafe_allow_html=True
        )

        # Symbol

        with c2:

            if st.button(
                row["symbol"],
                key=f"stock_{row['symbol']}"
            ):

                st.session_state.selected_ticker = row["symbol"]

                st.rerun()

            if row["repeat"]:

                st.markdown(
                    '<span class="repeat-dot">●</span>',
                    unsafe_allow_html=True
                )

        # LTP

        c3.markdown(
            f'<span class="metric">${row["price"]:.2f}</span>',
            unsafe_allow_html=True
        )

        # Change

        change_class = (
            "green"
            if row["change"] >= 0
            else "red"
        )

        c4.markdown(
            f'<span class="{change_class}">'
            f'{row["change"]:.2f}%'
            f'</span>',
            unsafe_allow_html=True
        )

        # RVOL

        c5.markdown(
            f'<span class="metric">'
            f'{row["rvol"]:.1f}'
            f'</span>',
            unsafe_allow_html=True
        )


# =========================================================
# TRADINGVIEW
# =========================================================

with chart_col:

    ticker = st.session_state.selected_ticker

    st.subheader(
        f"TradingView — {ticker}"
    )

    tradingview_html = f"""
    <div class="tradingview-widget-container"
         style="height:720px;width:100%">

      <div id="tradingview_chart"
           style="height:100%;width:100%">
      </div>

      <script type="text/javascript"
              src="https://s3.tradingview.com/tv.js">
      </script>

      <script type="text/javascript">

      new TradingView.widget({{
          "width": "100%",
          "height": "100%",
          "symbol": "NASDAQ:{ticker}",
          "interval": "1",
          "timezone": "America/New_York",
          "theme": "dark",
          "style": "1",
          "locale": "en",
          "toolbar_bg": "#11161d",
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

    components.html(
        tradingview_html,
        height=730
    )
