import streamlit as st
import yfinance as yf
import pandas as pd
import time
import streamlit.components.v1 as components


# =========================================================
# PAGE SETTINGS
# =========================================================

st.set_page_config(
    page_title="US Stock Screener",
    page_icon="📈",
    layout="wide"
)


# =========================================================
# 30 STOCK UNIVERSE
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

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None


# =========================================================
# CUSTOM CSS
# =========================================================

st.markdown("""
<style>

.block-container {
    padding-top: 1rem;
}

.stock-title {
    font-size: 28px;
    font-weight: bold;
    margin-bottom: 0px;
}

.stock-subtitle {
    color: gray;
    margin-bottom: 15px;
}

.metric-box {
    padding: 10px;
    border-radius: 10px;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# SIDEBAR FILTERS
# =========================================================

with st.sidebar:

    st.header("⚙ Filters")

    min_price = st.number_input(
        "Minimum Price",
        min_value=0.0,
        value=1.0,
        step=0.5
    )

    max_price = st.number_input(
        "Maximum Price",
        min_value=0.0,
        value=10000.0,
        step=10.0
    )

    min_volume = st.number_input(
        "Minimum Volume",
        min_value=0,
        value=100000,
        step=10000
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

    st.divider()

    scan_button = st.button(
        "🔍 Scan Stocks",
        use_container_width=True
    )

    st.divider()

    auto_refresh = st.checkbox(
        "Auto Refresh",
        value=False
    )

    refresh_seconds = st.selectbox(
        "Refresh Every",
        [30, 60, 120, 300],
        index=1
    )


# =========================================================
# DATA FUNCTION
# =========================================================

@st.cache_data(ttl=60)
def get_stock_data(ticker):

    try:

        stock = yf.Ticker(ticker)

        intraday = stock.history(
            period="5d",
            interval="5m",
            auto_adjust=True
        )

        daily = stock.history(
            period="1mo",
            interval="1d",
            auto_adjust=True
        )

        if intraday.empty or daily.empty:
            return None

        current_price = float(intraday["Close"].iloc[-1])

        previous_close = float(daily["Close"].iloc[-2])

        percent_change = (
            (current_price - previous_close)
            / previous_close
        ) * 100

        current_volume = float(
            intraday["Volume"].iloc[-1]
        )

        average_volume = float(
            intraday["Volume"].tail(78).mean()
        )

        if average_volume > 0:
            rvol = current_volume / average_volume
        else:
            rvol = 0

        total_volume_today = float(
            intraday["Volume"].sum()
        )

        return {
            "Ticker": ticker,
            "Price": round(current_price, 2),
            "% Change": round(percent_change, 2),
            "Current Volume": int(current_volume),
            "Total Volume": int(total_volume_today),
            "RVOL": round(rvol, 2)
        }

    except Exception as e:

        return None


# =========================================================
# SCANNER
# =========================================================

def scan_stocks():

    results = []

    progress_bar = st.progress(0)

    total_stocks = len(STOCKS)

    for index, ticker in enumerate(STOCKS.keys()):

        data = get_stock_data(ticker)

        if data is not None:

            price = data["Price"]
            total_volume = data["Total Volume"]
            percent_change = data["% Change"]
            rvol = data["RVOL"]

            if (
                price >= min_price
                and price <= max_price
                and total_volume >= min_volume
                and percent_change >= min_change
                and rvol >= min_rvol
            ):

                results.append(data)

        progress = int(
            ((index + 1) / total_stocks) * 100
        )

        progress_bar.progress(progress)

    progress_bar.empty()

    return results


# =========================================================
# HEADER
# =========================================================

st.markdown(
    '<div class="stock-title">📈 US STOCK SCREENER</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="stock-subtitle">30 Stock Momentum Scanner</div>',
    unsafe_allow_html=True
)


# =========================================================
# SCAN
# =========================================================

if scan_button or st.session_state.last_scan is None:

    with st.spinner("Scanning US stocks..."):

        results = scan_stocks()

        st.session_state.last_scan = results

else:

    results = st.session_state.last_scan


# =========================================================
# RESULTS DATAFRAME
# =========================================================

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
            "Price",
            "% Change",
            "Current Volume",
            "Total Volume",
            "RVOL"
        ]
    )


# =========================================================
# MAIN LAYOUT
# =========================================================

left_column, right_column = st.columns(
    [1, 3],
    gap="medium"
)


# =========================================================
# LEFT SIDE - STOCK LIST
# =========================================================

with left_column:

    st.subheader("Matching Stocks")

    if results_df.empty:

        st.info(
            "No stocks match the current filters."
        )

    else:

        for _, row in results_df.iterrows():

            ticker = row["Ticker"]

            company = STOCKS.get(
                ticker,
                ticker
            )

            button_text = (
                f"{ticker}  |  {company}"
            )

            if st.button(
                button_text,
                key=f"stock_{ticker}",
                use_container_width=True
            ):

                st.session_state.selected_ticker = ticker


# =========================================================
# RIGHT SIDE - CHART
# =========================================================

with right_column:

    selected = st.session_state.selected_ticker

    company_name = STOCKS.get(
        selected,
        selected
    )

    st.subheader(
        f"{selected} — {company_name}"
    )


    # ---------------------------------------------
    # SELECTED STOCK METRICS
    # ---------------------------------------------

    selected_row = results_df[
        results_df["Ticker"] == selected
    ]

    if not selected_row.empty:

        row = selected_row.iloc[0]

        m1, m2, m3, m4 = st.columns(4)

        m1.metric(
            "Price",
            f"${row['Price']}"
        )

        m2.metric(
            "% Change",
            f"{row['% Change']}%"
        )

        m3.metric(
            "RVOL",
            row["RVOL"]
        )

        m4.metric(
            "Total Volume",
            f"{int(row['Total Volume']):,}"
        )


    # ---------------------------------------------
    # TRADINGVIEW CHART
    # ---------------------------------------------

    tradingview_html = f"""
    <div class="tradingview-widget-container">

      <div
        id="tradingview_chart"
        style="height:650px;">
      </div>

      <script
        type="text/javascript"
        src="https://s3.tradingview.com/tv.js">
      </script>

      <script type="text/javascript">

      new TradingView.widget({{

        "width": "100%",
        "height": 650,

        "symbol": "NASDAQ:{selected}",

        "interval": "5",

        "timezone": "America/New_York",

        "theme": "dark",

        "style": "1",

        "locale": "en",

        "toolbar_bg": "#f1f3f6",

        "enable_publishing": false,

        "allow_symbol_change": true,

        "container_id": "tradingview_chart"

      }});

      </script>

    </div>
    """

    components.html(
        tradingview_html,
        height=670
    )


# =========================================================
# RESULTS TABLE
# =========================================================

st.divider()

st.subheader(
    f"Scanner Results ({len(results_df)})"
)

if not results_df.empty:

    st.dataframe(
        results_df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# AUTO REFRESH
# =========================================================

if auto_refresh:

    time.sleep(refresh_seconds)

    st.cache_data.clear()

    st.rerun()
