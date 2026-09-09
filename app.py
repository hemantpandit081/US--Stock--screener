import streamlit as st
import pandas as pd
import yfinance as yf
import streamlit.components.v1 as components
import time
from datetime import datetime
from zoneinfo import ZoneInfo


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="US Stock Momentum Scanner",
    layout="wide"
)

st.title("🇺🇸 US Stock Momentum Scanner")


# ============================================================
# MARKET STATUS
# ============================================================

def get_market_status():

    now = datetime.now(ZoneInfo("America/New_York"))
    current_time = now.time()

    premarket_start = datetime.strptime("04:00", "%H:%M").time()
    market_start = datetime.strptime("09:30", "%H:%M").time()
    market_end = datetime.strptime("16:00", "%H:%M").time()
    after_hours_end = datetime.strptime("20:00", "%H:%M").time()

    if premarket_start <= current_time < market_start:
        return "🟡 PRE-MARKET"

    elif market_start <= current_time < market_end:
        return "🟢 MARKET OPEN"

    elif market_end <= current_time < after_hours_end:
        return "🔵 AFTER-HOURS"

    return "🔴 MARKET CLOSED"


st.write("Market status:", get_market_status())


# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.header("Scanner Filters")

min_price = st.sidebar.number_input(
    "Minimum Price",
    min_value=0.01,
    value=1.00,
    step=0.50
)

max_price = st.sidebar.number_input(
    "Maximum Price",
    min_value=0.01,
    value=20.00,
    step=1.00
)

min_volume = st.sidebar.number_input(
    "Minimum Volume",
    min_value=0,
    value=100000,
    step=50000
)

min_rvol = st.sidebar.number_input(
    "Minimum RVOL",
    min_value=0.0,
    value=2.0,
    step=0.5
)

min_change = st.sidebar.number_input(
    "Minimum Change %",
    min_value=-100.0,
    value=2.0,
    step=1.0
)

refresh_seconds = st.sidebar.selectbox(
    "Refresh",
    [30, 60, 120, 300],
    index=1
)

scan_button = st.sidebar.button(
    "🔍 Scan Now",
    use_container_width=True
)


# ============================================================
# STOCK LIST
# ============================================================

@st.cache_data(ttl=300)
def get_stock_universe():

    return [
        "AAPL",
        "NVDA",
        "TSLA",
        "AMD",
        "AMZN",
        "META",
        "MSFT",
        "GOOGL",
        "NFLX",
        "PLTR",
        "MSTR",
        "COIN",
        "SMCI",
        "SOFI",
        "NIO",
        "RIVN",
        "LCID",
        "MARA",
        "RIOT",
        "IONQ",
        "BBAI",
        "SOUN",
        "AI",
        "HOOD",
        "RKLB",
        "GME",
        "AMC",
        "BB",
        "OPEN",
        "FFIE"
    ]


# ============================================================
# CALCULATE STOCK
# ============================================================

def calculate_stock(ticker):

    try:

        data = yf.Ticker(ticker).history(
            period="5d",
            interval="5m",
            prepost=False
        )

        if data.empty:
            return None

        data = data.dropna()

        if len(data) < 20:
            return None

        latest = data.iloc[-1]

        price = float(latest["Close"])

        volume = float(latest["Volume"])

        previous_close = float(data["Close"].iloc[-1])

        if previous_close == 0:
            return None

        change_percent = (
            (price - previous_close)
            / previous_close
            * 100
        )

        # Simple RVOL calculation
        average_volume = data["Volume"].rolling(
            20
        ).mean().iloc[-1]

        if average_volume and average_volume > 0:
            rvol = volume / average_volume
        else:
            rvol = 0

        return {
            "Ticker": ticker,
            "Price": round(price, 2),
            "Change %": round(change_percent, 2),
            "Volume": int(volume),
            "RVOL": round(rvol, 2),
            "Time": data.index[-1].strftime("%H:%M")
        }

    except Exception:
        return None


# ============================================================
# RUN SCANNER
# ============================================================

def run_scanner():

    stocks = get_stock_universe()

    results = []

    progress = st.progress(0)

    total = len(stocks)

    for i, ticker in enumerate(stocks):

        result = calculate_stock(ticker)

        if result is not None:
            results.append(result)

        progress.progress(
            (i + 1) / total
        )

    progress.empty()

    if results:
        return pd.DataFrame(results)

    return pd.DataFrame(
        columns=[
            "Ticker",
            "Price",
            "Change %",
            "Volume",
            "RVOL",
            "Time"
        ]
    )


# ============================================================
# RUN SCANNER
# ============================================================

if "scanner_data" not in st.session_state:

    st.session_state.scanner_data = pd.DataFrame()


if scan_button or st.session_state.scanner_data.empty:

    st.session_state.scanner_data = run_scanner()


df = st.session_state.scanner_data


# ============================================================
# APPLY FILTERS
# ============================================================

filtered = df.copy()

if not filtered.empty:

    filtered = filtered[
        (filtered["Price"] >= min_price) &
        (filtered["Price"] <= max_price) &
        (filtered["Volume"] >= min_volume) &
        (filtered["RVOL"] >= min_rvol) &
        (filtered["Change %"] >= min_change)
    ]

    filtered = filtered.sort_values(
        "RVOL",
        ascending=False
    )


# ============================================================
# SCANNER + TRADINGVIEW
# ============================================================

scanner_col, chart_col = st.columns(
    [40, 60]
)


# ============================================================
# LEFT - SCANNER
# ============================================================

with scanner_col:

    st.subheader("📊 Stock Scanner")

    if filtered.empty:

        st.warning(
            "No stocks match your filters."
        )

        st.info(
            "Try lowering RVOL or Change % filters."
        )

    else:

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True
        )

        selected_ticker = st.selectbox(
            "Select stock",
            filtered["Ticker"].tolist()
        )


# ============================================================
# RIGHT - TRADINGVIEW
# ============================================================

with chart_col:

    st.subheader("📈 TradingView Chart")

    if not filtered.empty:

        tradingview_html = f"""
        <div
            id="tradingview_chart"
            style="width:100%; height:700px;">
        </div>

        <script
            type="text/javascript"
            src="https://s3.tradingview.com/tv.js">
        </script>

        <script type="text/javascript">

        new TradingView.widget({{
            "width": "100%",
            "height": 700,
            "symbol": "NASDAQ:{selected_ticker}",
            "interval": "5",
            "timezone": "America/New_York",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "enable_publishing": false,
            "hide_top_toolbar": false,
            "hide_legend": false,
            "save_image": false,
            "container_id": "tradingview_chart"
        }});

        </script>
        """

        components.html(
            tradingview_html,
            height=720
        )

    else:

        st.info(
            "Select a stock from the scanner to display the chart."
        )


# ============================================================
# MANUAL REFRESH
# ============================================================

st.sidebar.markdown("---")

if st.sidebar.button(
    "🔄 Refresh Scanner",
    use_container_width=True
):

    st.session_state.scanner_data = run_scanner()

    st.rerun()
