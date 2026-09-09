import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import streamlit.components.v1 as components

# ---------------------------------------------------------
# PAGE SETTINGS
# ---------------------------------------------------------

st.set_page_config(
    page_title="US Stock Scanner",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------------------
# STOCK LIST
# ---------------------------------------------------------

STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META",
    "TSLA", "GOOGL", "GOOG", "AVGO", "AMD",
    "NFLX", "PLTR", "MU", "INTC", "SMCI",
    "ARM", "MSTR", "COIN", "HOOD", "SOFI",
    "RIVN", "NIO", "XPEV", "LI", "SOUN",
    "BBAI", "IONQ", "RKLB", "LUNR", "OKLO"
]

# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------

if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = "NVDA"

if "show_filters" not in st.session_state:
    st.session_state.show_filters = False

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

col1, col2 = st.columns([8, 2])

with col1:
    st.title("US Stock Scanner")

with col2:
    if st.button(
        "⚙ Filters",
        use_container_width=True
    ):
        st.session_state.show_filters = not st.session_state.show_filters

# ---------------------------------------------------------
# FILTERS
# ---------------------------------------------------------

if st.session_state.show_filters:

    st.markdown("### Scanner Filters")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        min_price = st.number_input(
            "Min Price",
            min_value=0.0,
            value=1.0,
            step=0.50
        )

    with c2:
        max_price = st.number_input(
            "Max Price",
            min_value=1.0,
            value=100.0,
            step=1.0
        )

    with c3:
        min_volume = st.number_input(
            "Minimum Volume",
            min_value=0,
            value=100000,
            step=10000
        )

    with c4:
        min_change = st.number_input(
            "Minimum % Change",
            value=0.0,
            step=0.5
        )

    with c5:
        min_rvol = st.number_input(
            "Minimum RVOL",
            min_value=0.0,
            value=0.0,
            step=0.5
        )

    st.divider()

# ---------------------------------------------------------
# SEARCH / SORT
# ---------------------------------------------------------

c1, c2 = st.columns([3, 2])

with c1:
    search = st.text_input(
        "Search stock",
        placeholder="Enter ticker..."
    ).upper().strip()

with c2:
    sort_by = st.selectbox(
        "Sort by",
        [
            "RVOL",
            "% Change",
            "Volume",
            "Price"
        ]
    )

# ---------------------------------------------------------
# DEFAULT FILTER VALUES
# ---------------------------------------------------------

if not st.session_state.show_filters:
    min_price = 1.0
    max_price = 100.0
    min_volume = 100000
    min_change = 0.0
    min_rvol = 0.0

# ---------------------------------------------------------
# DOWNLOAD DATA
# ---------------------------------------------------------

@st.cache_data(ttl=60)
def get_stock_data():

    try:

        data = yf.download(
            STOCKS,
            period="1mo",
            interval="1d",
            auto_adjust=False,
            group_by="ticker",
            threads=True,
            progress=False
        )

        results = []

        for ticker in STOCKS:

            try:

                if ticker not in data:
                    continue

                df = data[ticker].copy()

                if df.empty:
                    continue

                df = df.dropna()

                if len(df) < 2:
                    continue

                close = float(df["Close"].iloc[-1])
                volume = float(df["Volume"].iloc[-1])

                previous_volumes = df["Volume"].iloc[:-1].tail(20)

                if len(previous_volumes) > 0:
                    average_volume = float(
                        previous_volumes.mean()
                    )
                else:
                    average_volume = 0

                if average_volume > 0:
                    rvol = volume / average_volume
                else:
                    rvol = 0

                previous_close = float(
                    df["Close"].iloc[-2]
                )

                if previous_close > 0:
                    change = (
                        (close - previous_close)
                        / previous_close
                    ) * 100
                else:
                    change = 0

                results.append({
                    "Ticker": ticker,
                    "Price": close,
                    "Volume": int(volume),
                    "RVOL": round(rvol, 2),
                    "% Change": round(change, 2)
                })

            except Exception:
                continue

        return pd.DataFrame(results)

    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------

with st.spinner("Loading stocks..."):
    df = get_stock_data()

# ---------------------------------------------------------
# HANDLE EMPTY DATA
# ---------------------------------------------------------

if df.empty:

    st.warning(
        "No stock data available. Please try again."
    )

    st.stop()

# ---------------------------------------------------------
# APPLY FILTERS
# ---------------------------------------------------------

df = df[
    (df["Price"] >= min_price) &
    (df["Price"] <= max_price) &
    (df["Volume"] >= min_volume) &
    (df["% Change"] >= min_change) &
    (df["RVOL"] >= min_rvol)
]

# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

if search:

    df = df[
        df["Ticker"].str.contains(
            search,
            case=False,
            na=False
        )
    ]

# ---------------------------------------------------------
# SORT
# ---------------------------------------------------------

if sort_by == "RVOL":
    df = df.sort_values(
        "RVOL",
        ascending=False
    )

elif sort_by == "% Change":
    df = df.sort_values(
        "% Change",
        ascending=False
    )

elif sort_by == "Volume":
    df = df.sort_values(
        "Volume",
        ascending=False
    )

elif sort_by == "Price":
    df = df.sort_values(
        "Price",
        ascending=False
    )

# ---------------------------------------------------------
# MAIN SCREEN
# ---------------------------------------------------------

left, right = st.columns(
    [2, 8],
    gap="medium"
)

# ---------------------------------------------------------
# LEFT - STOCK LIST
# ---------------------------------------------------------

with left:

    st.markdown("### Stocks")

    if df.empty:

        st.info(
            "No stocks match your filters."
        )

    else:

        for _, row in df.iterrows():

            ticker = row["Ticker"]

            button_text = (
                f"{ticker}  "
                f"${row['Price']:.2f}  "
                f"{row['% Change']:+.1f}%"
            )

            if st.button(
                button_text,
                key=f"stock_{ticker}",
                use_container_width=True
            ):

                st.session_state.selected_stock = ticker

# ---------------------------------------------------------
# RIGHT - TRADINGVIEW CHART
# ---------------------------------------------------------

with right:

    selected = st.session_state.selected_stock

    st.markdown(
        f"### {selected}"
    )

    chart_html = f"""
    <div style="height:720px;width:100%;">
        <div
            class="tradingview-widget-container"
            style="height:100%;width:100%;"
        >

            <div
                class="tradingview-widget-container__widget"
                style="height:100%;width:100%;"
            ></div>

            <script
                type="text/javascript"
                src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
                async>
            {{
                "autosize": true,
                "symbol": "NASDAQ:{selected}",
                "interval": "5",
                "timezone": "Australia/Adelaide",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "allow_symbol_change": true,
                "calendar": false,
                "support_host": "https://www.tradingview.com"
            }}
            </script>

        </div>
    </div>
    """

    components.html(
        chart_html,
        height=730,
        scrolling=False
    )

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------

st.caption(
    "Prototype scanner using Yahoo Finance data • "
    "TradingView chart"
)
