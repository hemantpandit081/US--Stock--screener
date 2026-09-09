import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components
import html


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="US Stock Momentum Scanner",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# SCREEN / LAYOUT CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 0.4rem;
        padding-bottom: 0.4rem;
        padding-left: 0.6rem;
        padding-right: 0.6rem;
        max-width: 100%;
    }

    h1 {
        font-size: 1.45rem !important;
        margin-top: 0rem !important;
        margin-bottom: 0.15rem !important;
    }

    h2, h3 {
        margin-top: 0.15rem !important;
        margin-bottom: 0.15rem !important;
    }

    div[data-testid="stHorizontalBlock"] {
        gap: 0.4rem;
    }

    div[data-testid="stButton"] button {
        width: 100%;
        min-height: 27px;
        height: 27px;
        padding: 0px 3px;
        font-size: 0.78rem;
    }

    div[data-testid="stMarkdownContainer"] p {
        margin-bottom: 0.1rem;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# TITLE
# ============================================================

st.title("US Stock Momentum Scanner")


# ============================================================
# MARKET STATUS
# ============================================================

ny_time = datetime.now(
    ZoneInfo("America/New_York")
)

market_open = (
    ny_time.weekday() < 5
    and (
        ny_time.hour > 9
        or (
            ny_time.hour == 9
            and ny_time.minute >= 30
        )
    )
    and (
        ny_time.hour < 16
        or (
            ny_time.hour == 16
            and ny_time.minute == 0
        )
    )
)

if market_open:
    st.success(
        f"Market OPEN  |  New York: "
        f"{ny_time.strftime('%I:%M:%S %p')}"
    )
else:
    st.info(
        f"Market CLOSED  |  New York: "
        f"{ny_time.strftime('%I:%M:%S %p')}"
    )


# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.header("Scanner Filters")

min_price = st.sidebar.number_input(
    "Minimum Price",
    min_value=0.0,
    value=1.0,
    step=0.50
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
    step=50000
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
    "SCAN NOW",
    use_container_width=True
)


# ============================================================
# STOCK UNIVERSE
# ============================================================

STOCK_UNIVERSE = [
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
    "FFIE",
]


# ============================================================
# SESSION STATE
# ============================================================

if "scanner_data" not in st.session_state:
    st.session_state.scanner_data = pd.DataFrame()

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "AAPL"


# ============================================================
# STOCK CALCULATION
# ============================================================

def calculate_stock(symbol):

    try:

        ticker = yf.Ticker(symbol)

        # ----------------------------------------------------
        # 5 MINUTE DATA
        # ----------------------------------------------------

        intraday = ticker.history(
            period="5d",
            interval="5m",
            prepost=False,
            auto_adjust=False
        )

        if intraday.empty:
            return None

        # ----------------------------------------------------
        # DAILY DATA
        # ----------------------------------------------------

        daily = ticker.history(
            period="20d",
            interval="1d",
            auto_adjust=False
        )

        if daily.empty:
            return None

        intraday = intraday.copy()

        # Latest trading date
        latest_date = intraday.index[-1].date()

        today_data = intraday[
            intraday.index.date == latest_date
        ].copy()

        if today_data.empty:
            return None

        # ----------------------------------------------------
        # LTP
        # ----------------------------------------------------

        ltp = float(
            today_data["Close"].iloc[-1]
        )

        # ----------------------------------------------------
        # CURRENT SESSION VOLUME
        # ----------------------------------------------------

        session_volume = float(
            today_data["Volume"].sum()
        )

        # ----------------------------------------------------
        # PREVIOUS DAY CLOSE
        # ----------------------------------------------------

        if len(daily) >= 2:

            previous_close = float(
                daily["Close"].iloc[-2]
            )

        else:

            previous_close = float(
                daily["Close"].iloc[-1]
            )

        # ----------------------------------------------------
        # % CHANGE
        # ----------------------------------------------------

        if previous_close > 0:

            change_pct = (
                (ltp - previous_close)
                / previous_close
                * 100
            )

        else:

            change_pct = 0

        # ----------------------------------------------------
        # AVERAGE DAILY VOLUME
        # ----------------------------------------------------

        if len(daily) >= 6:

            previous_volumes = (
                daily["Volume"].iloc[-6:-1]
            )

        else:

            previous_volumes = (
                daily["Volume"].iloc[:-1]
            )

        if not previous_volumes.empty:

            avg_volume = float(
                previous_volumes.mean()
            )

        else:

            avg_volume = 0

        # ----------------------------------------------------
        # RELATIVE VOLUME
        # ----------------------------------------------------

        if avg_volume > 0:

            rvol = (
                session_volume
                / avg_volume
            )

        else:

            rvol = 0

        # ----------------------------------------------------
        # TIME
        # ----------------------------------------------------

        current_time = datetime.now(
            ZoneInfo("America/New_York")
        ).strftime("%H:%M")

        return {
            "Time": current_time,
            "Symbol": symbol,
            "LTP": ltp,
            "% Change": change_pct,
            "Rel Vol": rvol,
            "Volume": session_volume
        }

    except Exception:

        return None


# ============================================================
# RUN SCANNER
# ============================================================

def run_scanner():

    results = []

    progress = st.progress(0)

    total = len(STOCK_UNIVERSE)

    for i, symbol in enumerate(
        STOCK_UNIVERSE
    ):

        result = calculate_stock(symbol)

        if result is not None:
            results.append(result)

        progress.progress(
            int(
                ((i + 1) / total) * 100
            )
        )

    progress.empty()

    if results:

        return pd.DataFrame(results)

    return pd.DataFrame()


# ============================================================
# INITIAL SCAN
# ============================================================

if (
    scan_button
    or st.session_state.scanner_data.empty
):

    with st.spinner(
        "Scanning US stocks..."
    ):

        st.session_state.scanner_data = (
            run_scanner()
        )


# ============================================================
# MAIN TWO-COLUMN LAYOUT
# ============================================================

scanner_col, chart_col = st.columns(
    [40, 60],
    gap="small"
)


# ============================================================
# LEFT SIDE - SCANNER
# ============================================================

with scanner_col:

    st.subheader("Momentum Scanner")

    df = st.session_state.scanner_data.copy()

    if not df.empty:

        # ----------------------------------------------------
        # FILTERS
        # ----------------------------------------------------

        filtered = df[
            (df["LTP"] >= min_price)
            & (df["LTP"] <= max_price)
            & (df["Volume"] >= min_volume)
            & (df["Rel Vol"] >= min_rvol)
            & (df["% Change"] >= min_change)
        ].copy()

        # ----------------------------------------------------
        # SORT BY RELATIVE VOLUME
        # ----------------------------------------------------

        filtered = filtered.sort_values(
            "Rel Vol",
            ascending=False
        )

        st.caption(
            f"{len(filtered)} stocks matched"
        )

        # ----------------------------------------------------
        # TABLE HEADER
        # ----------------------------------------------------

        h1, h2, h3, h4, h5 = st.columns(
            [1.1, 1.3, 1.15, 1.25, 1.1]
        )

        h1.markdown("**Time**")
        h2.markdown("**Symbol**")
        h3.markdown("**LTP**")
        h4.markdown("**% Change**")
        h5.markdown("**Rel Vol**")

        st.divider()

        # ----------------------------------------------------
        # SCROLLABLE SCANNER
        # ----------------------------------------------------

        with st.container(
            height=610,
            border=False
        ):

            for _, row in filtered.iterrows():

                c1, c2, c3, c4, c5 = st.columns(
                    [1.1, 1.3, 1.15, 1.25, 1.1]
                )

                # TIME
                c1.write(
                    row["Time"]
                )

                # SYMBOL BUTTON
                if c2.button(
                    row["Symbol"],
                    key=f"stock_{row['Symbol']}",
                    use_container_width=True
                ):

                    st.session_state.selected_ticker = (
                        row["Symbol"]
                    )

                    st.rerun()

                # LTP
                c3.write(
                    f"${row['LTP']:.2f}"
                )

                # PERCENT CHANGE
                c4.write(
                    f"{row['% Change']:.2f}%"
                )

                # RELATIVE VOLUME
                # NUMBER ONLY
                c5.write(
                    f"{row['Rel Vol']:.2f}"
                )

    else:

        st.warning(
            "No scanner results available."
        )


# ============================================================
# RIGHT SIDE - TRADINGVIEW
# ============================================================

with chart_col:

    selected_ticker = (
        st.session_state.selected_ticker
    )

    st.subheader(
        f"TradingView — {selected_ticker}"
    )

    safe_symbol = html.escape(
        selected_ticker
    )

    # --------------------------------------------------------
    # TRADINGVIEW ADVANCED CHART
    # --------------------------------------------------------

    tradingview_html = f"""
    <div
        class="tradingview-widget-container"
        style="
            width:100%;
            height:650px;
            overflow:hidden;
        "
    >

        <div
            class="tradingview-widget-container__widget"
            style="
                width:100%;
                height:650px;
            "
        ></div>

        <script
            type="text/javascript"
            src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
            async
        >
        {{
            "autosize": true,
            "symbol": "NASDAQ:{safe_symbol}",
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
    """

    components.html(
        tradingview_html,
        height=660,
        scrolling=False
    )
