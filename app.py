import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="US Stock Momentum Scanner",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# COMPACT SCREEN LAYOUT
# =========================================================
st.markdown(
    """
    <style>

    /* Remove unnecessary page space */
    .block-container {
        padding-top: 0.05rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0.35rem !important;
        padding-right: 0.35rem !important;
        max-width: 100% !important;
    }

    /* Compact headings */
    h1 {
        font-size: 1.15rem !important;
        margin: 0rem !important;
        padding: 0rem !important;
    }

    h2 {
        font-size: 0.95rem !important;
        margin: 0rem !important;
        padding: 0rem !important;
    }

    h3 {
        font-size: 0.85rem !important;
        margin: 0rem !important;
        padding: 0rem !important;
    }

    /* Reduce vertical gaps */
    div[data-testid="stVerticalBlock"] {
        gap: 0.05rem !important;
    }

    div[data-testid="stHorizontalBlock"] {
        gap: 0.2rem !important;
    }

    /* Compact buttons */
    div[data-testid="stButton"] button {
        width: 100%;
        min-height: 23px !important;
        height: 23px !important;
        padding: 0px 2px !important;
        font-size: 0.72rem !important;
        line-height: 1 !important;
    }

    /* Compact text */
    div[data-testid="stMarkdownContainer"] p {
        margin: 0rem !important;
        padding: 0rem !important;
        font-size: 0.75rem !important;
    }

    /* Compact alerts */
    div[data-testid="stAlert"] {
        padding: 0.15rem 0.4rem !important;
        margin: 0rem !important;
    }

    /* Reduce dataframe/container spacing */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        padding: 0rem !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# DASHBOARD HEIGHT
# =========================================================
# Reduced so the whole dashboard fits on a normal laptop
DASHBOARD_HEIGHT = 500


# =========================================================
# MARKET STATUS
# =========================================================
ny_time = datetime.now(ZoneInfo("America/New_York"))

market_open = (
    ny_time.weekday() < 5
    and (
        ny_time.hour > 9
        or (ny_time.hour == 9 and ny_time.minute >= 30)
    )
    and ny_time.hour < 16
)

if market_open:
    market_status = "🟢 MARKET OPEN"
else:
    market_status = "🔴 MARKET CLOSED"


# =========================================================
# HEADER
# =========================================================
header_col1, header_col2 = st.columns([4, 1])

with header_col1:
    st.markdown(
        "### 🚀 US Stock Momentum Scanner"
    )

with header_col2:
    st.markdown(
        f"<div style='text-align:right;font-size:0.8rem;padding-top:5px;'>{market_status}</div>",
        unsafe_allow_html=True
    )


# =========================================================
# SIDEBAR FILTERS
# =========================================================
st.sidebar.header("Scanner Filters")

min_price = st.sidebar.number_input(
    "Minimum Price",
    min_value=0.0,
    value=1.0,
    step=0.5
)

max_price = st.sidebar.number_input(
    "Maximum Price",
    min_value=0.0,
    value=20.0,
    step=1.0
)

min_volume = st.sidebar.number_input(
    "Minimum Volume",
    min_value=0,
    value=100000,
    step=10000
)

min_rvol = st.sidebar.number_input(
    "Minimum Rel Vol",
    min_value=0.0,
    value=2.0,
    step=0.5
)

min_change = st.sidebar.number_input(
    "Minimum % Change",
    min_value=-100.0,
    value=2.0,
    step=0.5
)

scan_button = st.sidebar.button(
    "🔎 Scan Now",
    use_container_width=True
)


# =========================================================
# STOCK UNIVERSE
# =========================================================
stock_universe = [
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


# =========================================================
# CALCULATE STOCK
# =========================================================
def calculate_stock(symbol):

    try:

        ticker = yf.Ticker(symbol)

        # Intraday data
        intraday = ticker.history(
            period="5d",
            interval="5m",
            prepost=False,
            auto_adjust=False
        )

        # Daily data
        daily = ticker.history(
            period="20d",
            interval="1d",
            auto_adjust=False
        )

        if intraday.empty or daily.empty:
            return None

        intraday = intraday.dropna(subset=["Close", "Volume"])
        daily = daily.dropna(subset=["Close", "Volume"])

        if len(daily) < 6:
            return None

        # Latest price
        ltp = float(intraday["Close"].iloc[-1])

        # Latest trading session
        latest_date = intraday.index[-1].date()

        session_data = intraday[
            intraday.index.date == latest_date
        ]

        if session_data.empty:
            return None

        # Total session volume
        session_volume = float(
            session_data["Volume"].sum()
        )

        # Previous close
        previous_close = float(
            daily["Close"].iloc[-2]
        )

        # Percentage change
        change_pct = (
            (ltp - previous_close)
            / previous_close
        ) * 100

        # Average previous 5 daily volumes
        previous_volumes = daily["Volume"].iloc[-6:-1]

        average_daily_volume = float(
            previous_volumes.mean()
        )

        if average_daily_volume <= 0:
            return None

        # Relative volume
        rel_volume = (
            session_volume
            / average_daily_volume
        )

        current_time = datetime.now().strftime("%H:%M:%S")

        return {
            "Time": current_time,
            "Symbol": symbol,
            "LTP": ltp,
            "% Change": change_pct,
            "Rel Vol": rel_volume,
            "Volume": session_volume
        }

    except Exception:
        return None


# =========================================================
# RUN SCANNER
# =========================================================
def run_scanner():

    results = []

    progress = st.progress(0)

    total = len(stock_universe)

    for i, symbol in enumerate(stock_universe):

        result = calculate_stock(symbol)

        if result is not None:
            results.append(result)

        progress.progress(
            (i + 1) / total
        )

    progress.empty()

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)


# =========================================================
# SESSION STATE
# =========================================================
if "scanner_data" not in st.session_state:
    st.session_state.scanner_data = pd.DataFrame()

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "AAPL"


# =========================================================
# INITIAL SCAN
# =========================================================
if (
    scan_button
    or st.session_state.scanner_data.empty
):

    st.session_state.scanner_data = run_scanner()


# =========================================================
# FILTER RESULTS
# =========================================================
data = st.session_state.scanner_data.copy()

if not data.empty:

    filtered = data[
        (data["LTP"] >= min_price)
        & (data["LTP"] <= max_price)
        & (data["Volume"] >= min_volume)
        & (data["Rel Vol"] >= min_rvol)
        & (data["% Change"] >= min_change)
    ].copy()

    # Highest RVOL first
    filtered = filtered.sort_values(
        by="Rel Vol",
        ascending=False
    )

else:

    filtered = pd.DataFrame()


# =========================================================
# MAIN DASHBOARD
# =========================================================
scanner_col, chart_col = st.columns(
    [40, 60],
    gap="small"
)


# =========================================================
# LEFT — SCANNER
# =========================================================
with scanner_col:

    st.markdown("**📊 Scanner**")

    # Column headers
    h1, h2, h3, h4, h5 = st.columns(
        [1.1, 1.3, 1.15, 1.25, 1.1]
    )

    h1.markdown("**Time**")
    h2.markdown("**Symbol**")
    h3.markdown("**LTP**")
    h4.markdown("**% Change**")
    h5.markdown("**Rel Vol**")

    st.markdown("---")

    with st.container(
        height=DASHBOARD_HEIGHT - 45,
        border=False
    ):

        if filtered.empty:

            st.info(
                "No stocks match the current filters."
            )

        else:

            for _, row in filtered.iterrows():

                c1, c2, c3, c4, c5 = st.columns(
                    [1.1, 1.3, 1.15, 1.25, 1.1]
                )

                c1.write(
                    row["Time"]
                )

                if c2.button(
                    row["Symbol"],
                    key=f"stock_{row['Symbol']}",
                    use_container_width=True
                ):

                    st.session_state.selected_ticker = (
                        row["Symbol"]
                    )

                    st.rerun()

                c3.write(
                    f"${row['LTP']:.2f}"
                )

                c4.write(
                    f"{row['% Change']:.2f}%"
                )

                c5.write(
                    f"{row['Rel Vol']:.2f}"
                )


# =========================================================
# RIGHT — TRADINGVIEW
# =========================================================
with chart_col:

    selected = st.session_state.selected_ticker

    st.markdown(
        f"**📈 {selected} — TradingView**"
    )

    # Some stocks are listed on NYSE rather than NASDAQ
    nyse_symbols = {
        "GME",
        "AMC",
        "BB",
        "OPEN"
    }

    if selected in nyse_symbols:
        tv_symbol = f"NYSE:{selected}"
    else:
        tv_symbol = f"NASDAQ:{selected}"

    tradingview_html = f"""
    <!DOCTYPE html>

    <html>

    <head>

        <meta
            name="viewport"
            content="width=device-width,
                     initial-scale=1.0"
        >

        <style>

            html,
            body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                background: #131722;
            }}

            .tradingview-widget-container {{
                width: 100%;
                height: 100%;
                position: relative;
                overflow: hidden;
            }}

            .tradingview-widget-container__widget {{
                width: 100%;
                height: 100%;
            }}

        </style>

    </head>

    <body>

        <div class="tradingview-widget-container">

            <div
                class="tradingview-widget-container__widget">
            </div>

            <script
                type="text/javascript"
                src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
                async
            >

            {{
                "autosize": true,
                "symbol": "{tv_symbol}",
                "interval": "5",
                "timezone": "America/New_York",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "allow_symbol_change": true,
                "hide_top_toolbar": false,
                "hide_side_toolbar": false,
                "save_image": true,
                "details": false,
                "hotlist": false,
                "calendar": false,
                "withdateranges": true,
                "hide_volume": false,
                "support_host": "https://www.tradingview.com"
            }}

            </script>

        </div>

    </body>

    </html>
    """

    components.html(
        tradingview_html,
        height=DASHBOARD_HEIGHT,
        scrolling=False
    )
