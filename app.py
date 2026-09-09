import streamlit as st
import yfinance as yf
import pandas as pd
import time
import streamlit.components.v1 as components


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="US Stock Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# FORCE DARK LOOK
# =========================================================

st.markdown("""
<style>

html, body, [class*="css"] {
    font-family: Arial, sans-serif;
}

/* Main application background */
.stApp {
    background-color: #0e1117;
    color: #ffffff;
}

/* Main content */
.main {
    background-color: #0e1117;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #161a22;
}

/* Sidebar text */
section[data-testid="stSidebar"] * {
    color: #ffffff;
}

/* Header */
.header-title {
    font-size: 30px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 0px;
}

.header-subtitle {
    color: #9ca3af;
    font-size: 14px;
    margin-top: 3px;
    margin-bottom: 20px;
}

/* Stock buttons */
.stButton > button {
    width: 100%;
    border-radius: 7px;
    border: 1px solid #303641;
    background-color: #161a22;
    color: #ffffff;
    text-align: left;
    padding: 10px 12px;
}

.stButton > button:hover {
    border-color: #ff4b4b;
    color: #ffffff;
    background-color: #20252f;
}

/* Metrics */
[data-testid="stMetric"] {
    background-color: #161a22;
    border: 1px solid #303641;
    border-radius: 8px;
    padding: 10px;
}

/* Dataframe */
[data-testid="stDataFrame"] {
    background-color: #161a22;
}

/* Expander */
[data-testid="stExpander"] {
    background-color: #161a22;
    border: 1px solid #303641;
}

/* Selectbox and inputs */
div[data-baseweb="select"] > div {
    background-color: #161a22;
}

input {
    background-color: #161a22 !important;
    color: #ffffff !important;
}

/* Horizontal line */
hr {
    border-color: #303641;
}

/* Info box */
.stAlert {
    background-color: #161a22;
}

/* Hide Streamlit default footer */
footer {
    visibility: hidden;
}

/* Hide deploy button */
.stDeployButton {
    display: none;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# 30 US STOCKS
# =========================================================

STOCKS = {
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "AMD": "AMD",
    "AMZN": "Amazon",
    "META": "Meta",
    "GOOGL": "Alphabet",
    "NFLX": "Netflix",
    "PLTR": "Palantir",
    "COIN": "Coinbase",
    "MSTR": "MicroStrategy",
    "MARA": "MARA Holdings",
    "RIOT": "Riot Platforms",
    "HOOD": "Robinhood",
    "SMCI": "Super Micro Computer",
    "AVGO": "Broadcom",
    "MU": "Micron Technology",
    "INTC": "Intel",
    "ORCL": "Oracle",
    "CRM": "Salesforce",
    "UBER": "Uber",
    "ABNB": "Airbnb",
    "RIVN": "Rivian",
    "SOFI": "SoFi Technologies",
    "RKLB": "Rocket Lab",
    "IONQ": "IonQ",
    "ASTS": "AST SpaceMobile",
    "LUNR": "Intuitive Machines",
    "LCID": "Lucid"
}


# =========================================================
# SESSION STATE
# =========================================================

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "NVDA"

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []

if "has_scanned" not in st.session_state:
    st.session_state.has_scanned = False


# =========================================================
# DATA FUNCTION
# =========================================================

@st.cache_data(ttl=60)
def get_stock_data(ticker):

    try:

        stock = yf.Ticker(ticker)

        # 5-minute data
        intraday = stock.history(
            period="5d",
            interval="5m",
            auto_adjust=True
        )

        # Daily data
        daily = stock.history(
            period="1mo",
            interval="1d",
            auto_adjust=True
        )

        if intraday.empty or daily.empty:
            return None

        if len(daily) < 2:
            return None

        current_price = float(
            intraday["Close"].iloc[-1]
        )

        previous_close = float(
            daily["Close"].iloc[-2]
        )

        if previous_close <= 0:
            return None

        percent_change = (
            (current_price - previous_close)
            / previous_close
        ) * 100

        current_volume = float(
            intraday["Volume"].iloc[-1]
        )

        # Average recent 5-minute volume
        recent_volume = intraday["Volume"].tail(78)

        average_volume = float(
            recent_volume.mean()
        )

        if average_volume > 0:
            rvol = current_volume / average_volume
        else:
            rvol = 0

        # Total volume available in today's data
        today = intraday[
            intraday.index.date == intraday.index[-1].date()
        ]

        if today.empty:
            total_volume = current_volume
        else:
            total_volume = float(
                today["Volume"].sum()
            )

        return {
            "Ticker": ticker,
            "Company": STOCKS.get(ticker, ticker),
            "Price": round(current_price, 2),
            "% Change": round(percent_change, 2),
            "Volume": int(total_volume),
            "Current 5m Volume": int(current_volume),
            "RVOL": round(rvol, 2)
        }

    except Exception:
        return None


# =========================================================
# SCANNER FUNCTION
# =========================================================

def scan_stocks(
    min_price,
    max_price,
    min_volume,
    min_change,
    min_rvol
):

    results = []

    progress = st.progress(0)

    total = len(STOCKS)

    for number, ticker in enumerate(STOCKS.keys(), start=1):

        data = get_stock_data(ticker)

        if data is not None:

            if (
                data["Price"] >= min_price
                and data["Price"] <= max_price
                and data["Volume"] >= min_volume
                and data["% Change"] >= min_change
                and data["RVOL"] >= min_rvol
            ):

                results.append(data)

        progress.progress(
            number / total
        )

    progress.empty()

    return results


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        "## ⚙️ Filters"
    )

    st.markdown("---")

    min_price = st.number_input(
        "Minimum Price",
        min_value=0.0,
        value=1.0,
        step=1.0
    )

    max_price = st.number_input(
        "Maximum Price",
        min_value=1.0,
        value=1000.0,
        step=10.0
    )

    min_volume = st.number_input(
        "Minimum Volume",
        min_value=0,
        value=100000,
        step=50000
    )

    min_change = st.number_input(
        "Minimum % Change",
        value=0.0,
        step=0.5
    )

    min_rvol = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=1.0,
        step=0.1
    )

    st.markdown("---")

    scan_button = st.button(
        "🔍 SCAN STOCKS",
        use_container_width=True
    )

    st.markdown("---")

    if st.button(
        "🔄 Refresh Data",
        use_container_width=True
    ):

        st.cache_data.clear()
        st.rerun()


# =========================================================
# HEADER
# =========================================================

st.markdown(
    '<div class="header-title">📈 US STOCK SCREENER</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="header-subtitle">'
    '30-stock US momentum scanner'
    '</div>',
    unsafe_allow_html=True
)


# =========================================================
# RUN SCANNER
# =========================================================

if scan_button:

    with st.spinner("Scanning stocks..."):

        st.session_state.scan_results = scan_stocks(
            min_price,
            max_price,
            min_volume,
            min_change,
            min_rvol
        )

        st.session_state.has_scanned = True


# =========================================================
# RESULTS
# =========================================================

results = st.session_state.scan_results

if results:

    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        by="RVOL",
        ascending=False
    )

else:

    results_df = pd.DataFrame(
        columns=[
            "Ticker",
            "Company",
            "Price",
            "% Change",
            "Volume",
            "Current 5m Volume",
            "RVOL"
        ]
    )


# =========================================================
# TWO COLUMN LAYOUT
# =========================================================

left, right = st.columns(
    [1, 3],
    gap="medium"
)


# =========================================================
# LEFT SIDE
# =========================================================

with left:

    st.markdown("### Matching Stocks")

    if not st.session_state.has_scanned:

        st.info(
            "Open ⚙️ Filters and press "
            "SCAN STOCKS."
        )

    elif results_df.empty:

        st.warning(
            "No stocks match the current filters."
        )

    else:

        st.caption(
            f"{len(results_df)} stocks found"
        )

        for _, row in results_df.iterrows():

            ticker = row["Ticker"]

            company = row["Company"]

            label = f"{ticker}  •  {company}"

            if st.button(
                label,
                key=f"ticker_{ticker}",
                use_container_width=True
            ):

                st.session_state.selected_ticker = ticker

                st.rerun()


# =========================================================
# RIGHT SIDE
# =========================================================

with right:

    selected_ticker = (
        st.session_state.selected_ticker
    )

    selected_company = STOCKS.get(
        selected_ticker,
        selected_ticker
    )

    st.markdown(
        f"### {selected_ticker} — {selected_company}"
    )


    # =====================================================
    # SELECTED STOCK INFORMATION
    # =====================================================

    selected_data = None

    for item in results:

        if item["Ticker"] == selected_ticker:

            selected_data = item
            break


    if selected_data:

        c1, c2, c3, c4 = st.columns(4)

        c1.metric(
            "Price",
            f"${selected_data['Price']}"
        )

        c2.metric(
            "Change",
            f"{selected_data['% Change']}%"
        )

        c3.metric(
            "RVOL",
            f"{selected_data['RVOL']}x"
        )

        c4.metric(
            "Volume",
            f"{selected_data['Volume']:,}"
        )


    # =====================================================
    # TRADINGVIEW
    # =====================================================

    chart_html = f"""

    <div
        class="tradingview-widget-container"
        style="height:650px;width:100%;">

        <div
            id="tradingview_chart"
            style="height:650px;width:100%;">
        </div>

        <script
            type="text/javascript"
            src="https://s3.tradingview.com/tv.js">
        </script>

        <script type="text/javascript">

        new TradingView.widget({{

            "autosize": true,

            "symbol": "NASDAQ:{selected_ticker}",

            "interval": "5",

            "timezone": "America/New_York",

            "theme": "dark",

            "style": "1",

            "locale": "en",

            "enable_publishing": false,

            "hide_top_toolbar": false,

            "hide_legend": false,

            "allow_symbol_change": true,

            "save_image": false,

            "container_id": "tradingview_chart"

        }});

        </script>

    </div>

    """

    components.html(
        chart_html,
        height=670
    )


# =========================================================
# TABLE
# =========================================================

if not results_df.empty:

    st.markdown("---")

    st.markdown("### Scanner Results")

    display_df = results_df[
        [
            "Ticker",
            "Company",
            "Price",
            "% Change",
            "Volume",
            "RVOL"
        ]
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "Prototype scanner • Data provided by Yahoo Finance-compatible "
    "market data • TradingView chart"
)
