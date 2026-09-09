import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import streamlit.components.v1 as components

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="US Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

    /* Main background */
    .stApp {
        background-color: #0e1117;
    }

    /* Remove excessive top padding */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }

    /* Stock buttons */
    div.stButton > button {
        width: 100%;
        text-align: left;
        background-color: #151a21;
        color: white;
        border: 1px solid #252c35;
        border-radius: 5px;
        padding: 7px 10px;
        margin-bottom: 3px;
        height: 38px;
    }

    div.stButton > button:hover {
        background-color: #202832;
        border-color: #4b9cff;
        color: white;
    }

    /* Filter box */
    .filter-box {
        background-color: #151a21;
        border: 1px solid #252c35;
        border-radius: 7px;
        padding: 15px;
        margin-bottom: 12px;
    }

    /* Header */
    .scanner-header {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 10px;
    }

    .small-text {
        color: #8995a3;
        font-size: 12px;
    }

    /* Stock count */
    .stock-count {
        color: #8995a3;
        font-size: 12px;
        margin-bottom: 8px;
    }

</style>
""", unsafe_allow_html=True)

# ============================================================
# STOCK UNIVERSE
# ============================================================

STOCKS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "TSLA",
    "GOOGL",
    "GOOG",
    "AVGO",
    "AMD",
    "NFLX",
    "PLTR",
    "MU",
    "INTC",
    "SMCI",
    "ARM",
    "MSTR",
    "COIN",
    "HOOD",
    "SOFI",
    "RIVN",
    "NIO",
    "XPEV",
    "LI",
    "SOUN",
    "BBAI",
    "IONQ",
    "RKLB",
    "LUNR",
    "OKLO",
]

# ============================================================
# SESSION STATE
# ============================================================

if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = "AAPL"

if "show_filters" not in st.session_state:
    st.session_state.show_filters = False

if "scan_data" not in st.session_state:
    st.session_state.scan_data = pd.DataFrame()

# ============================================================
# FILTER TOGGLE
# ============================================================

top_left, top_right = st.columns([5, 1])

with top_left:
    st.markdown(
        '<div class="scanner-header">US Stock Scanner</div>',
        unsafe_allow_html=True
    )

with top_right:
    if st.button("⚙ Filters", use_container_width=True):
        st.session_state.show_filters = (
            not st.session_state.show_filters
        )
        st.rerun()

# ============================================================
# FILTERS
# ============================================================

min_price = 1.0
max_price = 100.0
min_volume = 100000
min_change = 0.0
min_rvol = 0.0
search_text = ""
sort_by = "RVOL"

if st.session_state.show_filters:

    with st.container():

        st.markdown(
            '<div class="filter-box">',
            unsafe_allow_html=True
        )

        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            min_price = st.number_input(
                "Min price",
                min_value=0.0,
                value=1.0,
                step=0.50
            )

        with c2:
            max_price = st.number_input(
                "Max price",
                min_value=0.0,
                value=100.0,
                step=1.0
            )

        with c3:
            min_volume = st.number_input(
                "Min volume",
                min_value=0,
                value=100000,
                step=100000
            )

        with c4:
            min_change = st.number_input(
                "Min % change",
                value=0.0,
                step=0.5
            )

        with c5:
            min_rvol = st.number_input(
                "Min RVOL",
                min_value=0.0,
                value=0.0,
                step=0.5
            )

        c6, c7 = st.columns([3, 1])

        with c6:
            search_text = st.text_input(
                "Search ticker",
                placeholder="Example: NVDA"
            )

        with c7:
            sort_by = st.selectbox(
                "Sort",
                [
                    "RVOL",
                    "% Change",
                    "Volume",
                    "Price"
                ]
            )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )

# ============================================================
# DATA DOWNLOAD
# ============================================================

@st.cache_data(ttl=60, show_spinner=False)
def download_market_data(symbols):

    try:

        data = yf.download(
            list(symbols),
            period="1mo",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True
        )

        return data

    except Exception as e:

        st.error(f"Data error: {e}")

        return pd.DataFrame()


# ============================================================
# BUILD SCANNER DATA
# ============================================================

def build_scanner_data():

    data = download_market_data(
        tuple(STOCKS)
    )

    results = []

    if data.empty:
        return pd.DataFrame()

    for symbol in STOCKS:

        try:

            if isinstance(data.columns, pd.MultiIndex):

                if symbol not in data.columns.get_level_values(0):
                    continue

                df = data[symbol].copy()

            else:

                df = data.copy()

            df = df.dropna(
                subset=["Close", "Volume"]
            )

            if len(df) < 2:
                continue

            latest = df.iloc[-1]

            price = float(
                latest["Close"]
            )

            volume = float(
                latest["Volume"]
            )

            previous_close = float(
                df.iloc[-2]["Close"]
            )

            if previous_close <= 0:
                continue

            change = (
                (price - previous_close)
                / previous_close
            ) * 100

            # Previous 20 trading days
            previous_volumes = (
                df["Volume"]
                .iloc[:-1]
                .tail(20)
            )

            average_volume = (
                previous_volumes.mean()
                if len(previous_volumes)
                else 0
            )

            if average_volume > 0:
                rvol = (
                    volume /
                    average_volume
                )
            else:
                rvol = 0

            results.append({

                "Ticker": symbol,

                "Price": round(
                    price,
                    2
                ),

                "Change": round(
                    change,
                    2
                ),

                "Volume": int(
                    volume
                ),

                "RVOL": round(
                    rvol,
                    2
                )

            })

        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)


# ============================================================
# RUN SCANNER
# ============================================================

with st.spinner("Scanning US stocks..."):

    scanner = build_scanner_data()

# ============================================================
# FILTER DATA
# ============================================================

if not scanner.empty:

    scanner = scanner[
        (scanner["Price"] >= min_price) &
        (scanner["Price"] <= max_price) &
        (scanner["Volume"] >= min_volume) &
        (scanner["Change"] >= min_change) &
        (scanner["RVOL"] >= min_rvol)
    ]

    if search_text:

        scanner = scanner[
            scanner["Ticker"]
            .str.contains(
                search_text.upper(),
                na=False
            )
        ]

    # Sorting

    if sort_by == "RVOL":

        scanner = scanner.sort_values(
            "RVOL",
            ascending=False
        )

    elif sort_by == "% Change":

        scanner = scanner.sort_values(
            "Change",
            ascending=False
        )

    elif sort_by == "Volume":

        scanner = scanner.sort_values(
            "Volume",
            ascending=False
        )

    elif sort_by == "Price":

        scanner = scanner.sort_values(
            "Price",
            ascending=False
        )

# ============================================================
# LAYOUT
# ============================================================

left, right = st.columns(
    [1.0, 3.2],
    gap="small"
)

# ============================================================
# LEFT SIDE - STOCK LIST
# ============================================================

with left:

    st.markdown(
        f'<div class="stock-count">'
        f'{len(scanner)} stocks'
        f'</div>',
        unsafe_allow_html=True
    )

    if scanner.empty:

        st.warning(
            "No stocks match the filters."
        )

    else:

        for _, row in scanner.iterrows():

            ticker = row["Ticker"]

            button_text = ticker

            if st.button(
                button_text,
                key=f"stock_{ticker}",
                use_container_width=True
            ):

                st.session_state.selected_stock = ticker

                st.rerun()

# ============================================================
# RIGHT SIDE - TRADINGVIEW
# ============================================================

with right:

    selected = (
        st.session_state.selected_stock
    )

    st.markdown(
        f"""
        <div style="
            font-size:15px;
            font-weight:600;
            margin-bottom:5px;
        ">
            {selected}
        </div>
        """,
        unsafe_allow_html=True
    )

    tradingview_html = f"""
    <div class="tradingview-widget-container"
         style="height:calc(100vh - 100px);width:100%">

        <div id="tradingview_chart"
             style="height:100%;width:100%">
        </div>

        <script
            type="text/javascript"
            src="https://s3.tradingview.com/tv.js">
        </script>

        <script type="text/javascript">

            new TradingView.widget({{

                "autosize": true,

                "symbol": "NASDAQ:{selected}",

                "interval": "5",

                "timezone": "America/New_York",

                "theme": "dark",

                "style": "1",

                "locale": "en",

                "toolbar_bg": "#0e1117",

                "enable_publishing": false,

                "hide_top_toolbar": false,

                "hide_legend": false,

                "save_image": false,

                "container_id": "tradingview_chart"

            }});

        </script>

    </div>
    """

    components.html(
        tradingview_html,
        height=750,
        scrolling=False
    )

# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div style="
        position:fixed;
        bottom:3px;
        left:10px;
        font-size:10px;
        color:#5f6b77;
    ">
        Prototype data: Yahoo Finance / yfinance
    </div>
    """,
    unsafe_allow_html=True
)
