import streamlit as st
import pandas as pd
import yfinance as yf
import streamlit.components.v1 as components
from datetime import datetime
from zoneinfo import ZoneInfo
import time

# --------------------------------------------------
# PAGE SETTINGS
# --------------------------------------------------

st.set_page_config(
    page_title="US Stock Momentum Scanner",
    layout="wide"
)

st.title("🇺🇸 US Stock Momentum Scanner")

# --------------------------------------------------
# STOCK UNIVERSE
# --------------------------------------------------

# --------------------------------------------------
# AUTOMATIC US STOCK UNIVERSE
# --------------------------------------------------

@st.cache_data(ttl=300)
def get_stock_universe():

    try:
        query = yf.EquityQuery(
            "and",
            [
                yf.EquityQuery("eq", ["region", "us"]),
                yf.EquityQuery("gte", ["intradayprice", 1]),
                yf.EquityQuery("lte", ["intradayprice", 100]),
                yf.EquityQuery("gte", ["dayvolume", 100000])
            ]
        )

        response = yf.screen(
            query,
            size=250,
            sortField="dayvolume",
            sortAsc=False
        )

        quotes = response.get("quotes", [])

        stocks = []

        for quote in quotes:
            symbol = quote.get("symbol")

            if symbol:
                stocks.append(symbol)

        return stocks

    except Exception as e:

        st.warning(
            f"Could not load automatic stock universe: {e}"
        )

        return []

# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.header("⚙️ Scanner Filters")

min_price = st.sidebar.number_input(
    "Minimum Price ($)",
    min_value=0.01,
    value=1.00,
    step=0.10
)

max_price = st.sidebar.number_input(
    "Maximum Price ($)",
    min_value=0.01,
    value=20.00,
    step=0.50
)

min_volume = st.sidebar.number_input(
    "Minimum Volume",
    min_value=0,
    value=100000,
    step=10000
)

min_rvol = st.sidebar.number_input(
    "Minimum RVOL (x)",
    min_value=0.0,
    value=2.0,
    step=0.5
)

min_change = st.sidebar.number_input(
    "Minimum Change (%)",
    value=2.0,
    step=0.5
)

refresh_seconds = st.sidebar.selectbox(
    "Auto Refresh",
    [30, 60, 120, 300],
    index=1
)

scan_button = st.sidebar.button(
    "🔄 Scan Now",
    use_container_width=True
)

# --------------------------------------------------
# US MARKET TIME
# --------------------------------------------------

us_tz = ZoneInfo("America/New_York")
now_us = datetime.now(us_tz)

market_open = now_us.replace(
    hour=9,
    minute=30,
    second=0,
    microsecond=0
)

market_close = now_us.replace(
    hour=16,
    minute=0,
    second=0,
    microsecond=0
)

premarket_start = now_us.replace(
    hour=4,
    minute=0,
    second=0,
    microsecond=0
)

afterhours_close = now_us.replace(
    hour=20,
    minute=0,
    second=0,
    microsecond=0
)

if premarket_start <= now_us < market_open:
    market_status = "🟡 PREMARKET"
elif market_open <= now_us < market_close:
    market_status = "🟢 MARKET OPEN"
elif market_close <= now_us < afterhours_close:
    market_status = "🔵 AFTER-HOURS"
else:
    market_status = "🔴 MARKET CLOSED"

st.info(
    f"US Market Status: **{market_status}**  |  "
    f"US Time: **{now_us.strftime('%Y-%m-%d %I:%M:%S %p')}**"
)

# --------------------------------------------------
# DOWNLOAD DATA
# --------------------------------------------------

@st.cache_data(ttl=60)
def get_intraday_data(ticker):

    try:

        data = yf.download(
            ticker,
            period="5d",
            interval="5m",
            prepost=False,
            progress=False,
            auto_adjust=False
        )

        if data.empty:
            return None

        # Handle Yahoo multi-index columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        data = data.dropna()

        return data

    except Exception:
        return None


@st.cache_data(ttl=300)
def get_previous_close(ticker):

    try:

        data = yf.download(
            ticker,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=False
        )

        if data.empty:
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        if len(data) < 2:
            return None

        return float(data["Close"].iloc[-2])

    except Exception:
        return None


# --------------------------------------------------
# CALCULATE RVOL
# --------------------------------------------------

def calculate_stock(ticker):

    data = get_intraday_data(ticker)

    if data is None or data.empty:
        return None

    try:

        # Convert time to US Eastern
        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC")

        data.index = data.index.tz_convert("America/New_York")

        # Date and time columns
        data["Date"] = data.index.date
        data["Time"] = data.index.strftime("%H:%M")

        # Get trading days
        trading_days = sorted(data["Date"].unique())

        if len(trading_days) < 2:
            return None

        current_day = trading_days[-1]

        today = data[data["Date"] == current_day].copy()

        if today.empty:
            return None

        # Today's cumulative volume
        today["CumVolume"] = today["Volume"].cumsum()

        latest = today.iloc[-1]

        current_price = float(latest["Close"])
        current_volume = int(today["Volume"].sum())

        latest_time = latest["Time"]

        # ----------------------------------------------
        # Historical cumulative volume at same time
        # ----------------------------------------------

        historical_cumulative = []

        previous_days = trading_days[:-1]

        for day in previous_days:

            day_data = data[data["Date"] == day].copy()

            if day_data.empty:
                continue

            day_data["CumVolume"] = day_data["Volume"].cumsum()

            same_time = day_data[
                day_data["Time"] <= latest_time
            ]

            if not same_time.empty:

                historical_cumulative.append(
                    float(same_time["Volume"].sum())
                )

        if historical_cumulative:

            average_volume = sum(
                historical_cumulative
            ) / len(historical_cumulative)

            if average_volume > 0:
                rvol = current_volume / average_volume
            else:
                rvol = 0

        else:
            rvol = 0

        # ----------------------------------------------
        # Previous close / percentage change
        # ----------------------------------------------

        previous_close = get_previous_close(ticker)

        if previous_close and previous_close > 0:

            change_percent = (
                (current_price - previous_close)
                / previous_close
            ) * 100

        else:
            change_percent = 0

        return {
            "Ticker": ticker,
            "Price": current_price,
            "Change %": change_percent,
            "Volume": current_volume,
            "RVOL": rvol,
            "Time": latest_time
        }

    except Exception:
        return None


# --------------------------------------------------
# SCAN MARKET
# --------------------------------------------------

def run_scanner():

    results = []

    progress = st.progress(0)

    for i, ticker in enumerate(stocks):

        result = calculate_stock(ticker)

        if result is not None:
            results.append(result)

        progress.progress(
            int((i + 1) / len(stocks) * 100)
        )

    progress.empty()

    return pd.DataFrame(results)


# --------------------------------------------------
# RUN SCAN
# --------------------------------------------------

if (
    "scanner_data" not in st.session_state
    or scan_button
):

    with st.spinner("🔎 Finding active US stocks..."):

        stocks = get_stock_universe()

        if stocks:

            st.session_state.scanner_data = run_scanner()

        else:

            st.session_state.scanner_data = pd.DataFrame()

df = st.session_state.scanner_data


# APPLY FILTERS

filtered = results.copy()

if not filtered.empty:
    filtered = filtered[
        (filtered["Price"] >= min_price) &
        (filtered["Price"] <= max_price) &
        (filtered["Volume"] >= min_volume) &
        (filtered["RVOL"] >= min_rvol) &
        (filtered["Change %"] >= min_change)
    ]

# Sort by RVOL
if not filtered.empty:
    filtered = filtered.sort_values("RVOL", ascending=False)


# =========================
# SCANNER + TRADINGVIEW
# =========================

scanner_col, chart_col = st.columns([40, 60])


# -------------------------
# LEFT SIDE - SCANNER
# -------------------------

with scanner_col:

    st.subheader("📊 Stock Scanner")

    if filtered.empty:

        st.warning("No stocks match your filters.")

    else:

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True
        )

        # Select stock
        selected_ticker = st.selectbox(
            "Select stock for chart",
            filtered["Ticker"].tolist()
        )


# -------------------------
# RIGHT SIDE - TRADINGVIEW
# -------------------------

with chart_col:

    st.subheader("📈 TradingView Chart")

    if not filtered.empty:

        tradingview_html = f"""
        <div id="tradingview_chart"
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
            "toolbar_bg": "#1e1e1e",
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


# =========================
# AUTO REFRESH
# =========================

if auto_refresh:

    time.sleep(refresh_seconds)

    st.rerun()
