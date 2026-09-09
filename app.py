import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components
import json
import os


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="US Stock Momentum Scanner",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 0.8rem;
    padding-bottom: 0.5rem;
    padding-left: 1rem;
    padding-right: 1rem;
}

h1 {
    margin-bottom: 0.2rem;
}

h2, h3 {
    margin-top: 0.2rem;
    margin-bottom: 0.4rem;
}

div[data-testid="stHorizontalBlock"] {
    gap: 0.5rem;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# SETTINGS
# ============================================================

SETTINGS_FILE = "scanner_settings.json"

DEFAULT_SETTINGS = {
    "min_price": 1.0,
    "max_price": 20.0,
    "min_volume": 100000,
    "min_rvol": 2.0,
    "min_change": 2.0
}


# ============================================================
# LOAD SAVED SETTINGS
# ============================================================

def load_saved_settings():

    if os.path.exists(SETTINGS_FILE):

        try:

            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)

            settings = DEFAULT_SETTINGS.copy()
            settings.update(saved)

            return settings

        except Exception:
            return DEFAULT_SETTINGS.copy()

    return DEFAULT_SETTINGS.copy()


# ============================================================
# SAVE SETTINGS
# ============================================================

def save_settings(settings):

    try:

        with open(SETTINGS_FILE, "w") as f:

            json.dump(
                settings,
                f,
                indent=4
            )

        return True

    except Exception as e:

        st.error(
            f"Could not save settings: {e}"
        )

        return False


# ============================================================
# LOAD SETTINGS ON STARTUP
# ============================================================

if "settings_loaded" not in st.session_state:

    saved_settings = load_saved_settings()

    st.session_state.min_price = (
        saved_settings["min_price"]
    )

    st.session_state.max_price = (
        saved_settings["max_price"]
    )

    st.session_state.min_volume = (
        saved_settings["min_volume"]
    )

    st.session_state.min_rvol = (
        saved_settings["min_rvol"]
    )

    st.session_state.min_change = (
        saved_settings["min_change"]
    )

    st.session_state.settings_loaded = True


# ============================================================
# SESSION STATE
# ============================================================

if "scanner_data" not in st.session_state:
    st.session_state.scanner_data = []


if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "AAPL"


if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None


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
    "FFIE"

]


# ============================================================
# MARKET TIME
# ============================================================

def get_market_time():

    return datetime.now(
        ZoneInfo("America/New_York")
    )


def market_is_open():

    now = get_market_time()

    if now.weekday() >= 5:
        return False

    current_time = now.time()

    market_open = datetime.strptime(
        "09:30",
        "%H:%M"
    ).time()

    market_close = datetime.strptime(
        "16:00",
        "%H:%M"
    ).time()

    return (
        market_open
        <= current_time
        <= market_close
    )


# ============================================================
# CALCULATE STOCK DATA
# ============================================================

def calculate_stock(symbol):

    try:

        # ----------------------------------------------------
        # 5 MINUTE DATA
        # ----------------------------------------------------

        intraday = yf.Ticker(
            symbol
        ).history(
            period="5d",
            interval="5m",
            prepost=False,
            auto_adjust=False
        )

        if intraday.empty:
            return None

        intraday = intraday.dropna(
            subset=[
                "Close",
                "Volume"
            ]
        )

        if intraday.empty:
            return None

        # ----------------------------------------------------
        # LATEST SESSION
        # ----------------------------------------------------

        latest_date = (
            intraday.index[-1].date()
        )

        session_data = intraday[
            intraday.index.date == latest_date
        ].copy()

        if session_data.empty:
            return None

        # ----------------------------------------------------
        # LTP
        # ----------------------------------------------------

        ltp = float(
            session_data[
                "Close"
            ].iloc[-1]
        )

        # ----------------------------------------------------
        # FULL SESSION VOLUME
        # ----------------------------------------------------

        session_volume = float(
            session_data[
                "Volume"
            ].sum()
        )

        # ----------------------------------------------------
        # DAILY DATA
        # ----------------------------------------------------

        daily = yf.Ticker(
            symbol
        ).history(
            period="20d",
            interval="1d",
            prepost=False,
            auto_adjust=False
        )

        if daily.empty:
            return None

        daily = daily.dropna(
            subset=[
                "Close",
                "Volume"
            ]
        )

        if len(daily) < 6:
            return None

        # ----------------------------------------------------
        # PREVIOUS CLOSE
        # ----------------------------------------------------

        previous_close = float(
            daily[
                "Close"
            ].iloc[-2]
        )

        # ----------------------------------------------------
        # PERCENT CHANGE
        # ----------------------------------------------------

        percent_change = (

            (
                ltp
                - previous_close
            )
            / previous_close
            * 100

        )

        # ----------------------------------------------------
        # PREVIOUS 5 DAYS AVERAGE VOLUME
        # ----------------------------------------------------

        previous_volumes = daily[
            "Volume"
        ].iloc[-6:-1]

        average_daily_volume = float(
            previous_volumes.mean()
        )

        # ----------------------------------------------------
        # RELATIVE VOLUME
        # ----------------------------------------------------

        if average_daily_volume > 0:

            relative_volume = (
                session_volume
                / average_daily_volume
            )

        else:

            relative_volume = 0

        # ----------------------------------------------------
        # TIME
        # ----------------------------------------------------

        latest_timestamp = (
            session_data.index[-1]
        )

        try:

            latest_timestamp = (
                latest_timestamp.tz_convert(
                    "America/New_York"
                )
            )

        except Exception:

            pass

        time_string = (
            latest_timestamp.strftime(
                "%H:%M"
            )
        )

        # ----------------------------------------------------
        # RETURN DATA
        # ----------------------------------------------------

        return {

            "Time": time_string,

            "Symbol": symbol,

            "LTP": ltp,

            "% Change": percent_change,

            "Rel Vol": relative_volume,

            "Volume": session_volume

        }

    except Exception as e:

        print(
            f"Error calculating {symbol}: {e}"
        )

        return None


# ============================================================
# RUN SCANNER
# ============================================================

def run_scanner():

    results = []

    progress = st.progress(0)

    status = st.empty()

    total = len(
        STOCK_UNIVERSE
    )

    for i, symbol in enumerate(
        STOCK_UNIVERSE
    ):

        status.text(
            f"Scanning {symbol}..."
        )

        result = calculate_stock(
            symbol
        )

        if result is not None:

            results.append(
                result
            )

        progress.progress(
            (i + 1) / total
        )

    progress.empty()

    status.empty()

    return results


# ============================================================
# TITLE
# ============================================================

st.title(
    "US Stock Momentum Scanner"
)


# ============================================================
# MARKET STATUS
# ============================================================

market_time = get_market_time()

if market_is_open():

    st.success(
        "US Market OPEN • "
        + market_time.strftime(
            "%H:%M:%S"
        )
        + " ET"
    )

else:

    st.info(
        "US Market CLOSED • "
        + market_time.strftime(
            "%H:%M:%S"
        )
        + " ET"
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "Scanner Filters"
    )

    # --------------------------------------------------------
    # MINIMUM PRICE
    # --------------------------------------------------------

    st.session_state.min_price = (
        st.number_input(
            "Minimum Price",
            min_value=0.0,
            value=float(
                st.session_state.min_price
            ),
            step=0.50
        )
    )

    # --------------------------------------------------------
    # MAXIMUM PRICE
    # --------------------------------------------------------

    st.session_state.max_price = (
        st.number_input(
            "Maximum Price",
            min_value=0.0,
            value=float(
                st.session_state.max_price
            ),
            step=0.50
        )
    )

    # --------------------------------------------------------
    # MINIMUM VOLUME
    # --------------------------------------------------------

    st.session_state.min_volume = (
        st.number_input(
            "Minimum Volume",
            min_value=0,
            value=int(
                st.session_state.min_volume
            ),
            step=10000
        )
    )

    # --------------------------------------------------------
    # MINIMUM RELATIVE VOLUME
    # --------------------------------------------------------

    st.session_state.min_rvol = (
        st.number_input(
            "Minimum Rel Vol",
            min_value=0.0,
            value=float(
                st.session_state.min_rvol
            ),
            step=0.5
        )
    )

    # --------------------------------------------------------
    # MINIMUM % CHANGE
    # --------------------------------------------------------

    st.session_state.min_change = (
        st.number_input(
            "Minimum % Change",
            min_value=-100.0,
            value=float(
                st.session_state.min_change
            ),
            step=0.5
        )
    )

    st.markdown("---")

    # ========================================================
    # SAVE SETTINGS
    # ========================================================

    if st.button(
        "💾 Save Filter Settings",
        use_container_width=True
    ):

        settings_to_save = {

            "min_price":
                st.session_state.min_price,

            "max_price":
                st.session_state.max_price,

            "min_volume":
                st.session_state.min_volume,

            "min_rvol":
                st.session_state.min_rvol,

            "min_change":
                st.session_state.min_change

        }

        if save_settings(
            settings_to_save
        ):

            st.success(
                "Filter settings saved!"
            )

    # ========================================================
    # RESET SETTINGS
    # ========================================================

    if st.button(
        "↩ Reset to Default",
        use_container_width=True
    ):

        st.session_state.min_price = (
            DEFAULT_SETTINGS["min_price"]
        )

        st.session_state.max_price = (
            DEFAULT_SETTINGS["max_price"]
        )

        st.session_state.min_volume = (
            DEFAULT_SETTINGS["min_volume"]
        )

        st.session_state.min_rvol = (
            DEFAULT_SETTINGS["min_rvol"]
        )

        st.session_state.min_change = (
            DEFAULT_SETTINGS["min_change"]
        )

        st.rerun()

    st.markdown("---")

    # ========================================================
    # SCAN BUTTON
    # ========================================================

    scan_button = st.button(
        "🔍 Scan Now",
        use_container_width=True,
        type="primary"
    )


# ============================================================
# RUN SCAN
# ============================================================

if scan_button:

    with st.spinner(
        "Scanning US stocks..."
    ):

        st.session_state.scanner_data = (
            run_scanner()
        )

        st.session_state.last_scan_time = (
            datetime.now().strftime(
                "%H:%M:%S"
            )
        )


# ============================================================
# LAST SCAN TIME
# ============================================================

if st.session_state.last_scan_time:

    st.caption(
        "Last scan: "
        + st.session_state.last_scan_time
    )


# ============================================================
# MAIN LAYOUT
#
# LEFT  = 35%
# RIGHT = 65%
# ============================================================

scanner_col, chart_col = st.columns(
    [35, 65]
)


# ============================================================
# SCANNER — LEFT 35%
# ============================================================

with scanner_col:

    st.markdown(
        "### Scanner"
    )

    data = (
        st.session_state.scanner_data
    )

    if data:

        filtered = []

        # ----------------------------------------------------
        # APPLY FILTERS
        # ----------------------------------------------------

        for row in data:

            if (

                row["LTP"]
                >= st.session_state.min_price

                and

                row["LTP"]
                <= st.session_state.max_price

                and

                row["Volume"]
                >= st.session_state.min_volume

                and

                row["Rel Vol"]
                >= st.session_state.min_rvol

                and

                row["% Change"]
                >= st.session_state.min_change

            ):

                filtered.append(
                    row
                )

        # ----------------------------------------------------
        # SORT BY RELATIVE VOLUME
        # ----------------------------------------------------

        filtered = sorted(
            filtered,
            key=lambda x: x["Rel Vol"],
            reverse=True
        )

        # ----------------------------------------------------
        # TABLE HEADER
        # ----------------------------------------------------

        h1, h2, h3, h4, h5 = st.columns(
            [
                0.75,
                1.0,
                1.0,
                1.0,
                1.0
            ]
        )

        h1.markdown(
            "**Time**"
        )

        h2.markdown(
            "**Symbol**"
        )

        h3.markdown(
            "**LTP**"
        )

        h4.markdown(
            "**% Change**"
        )

        h5.markdown(
            "**Rel Vol**"
        )

        # ----------------------------------------------------
        # STOCK ROWS
        # ----------------------------------------------------

        for row in filtered:

            c1, c2, c3, c4, c5 = st.columns(
                [
                    0.75,
                    1.0,
                    1.0,
                    1.0,
                    1.0
                ]
            )

            c1.write(
                row["Time"]
            )

            # ------------------------------------------------
            # CLICKABLE SYMBOL
            # ------------------------------------------------

            if c2.button(
                row["Symbol"],
                key=(
                    "ticker_"
                    + row["Symbol"]
                ),
                use_container_width=True
            ):

                st.session_state.selected_ticker = (
                    row["Symbol"]
                )

                st.rerun()

            c3.write(
                f"{row['LTP']:.2f}"
            )

            c4.write(
                f"{row['% Change']:.2f}%"
            )

            # Rel Vol number only
            c5.write(
                f"{row['Rel Vol']:.1f}"
            )

        # ----------------------------------------------------
        # MATCH COUNT
        # ----------------------------------------------------

        st.caption(
            f"{len(filtered)} stocks matched"
        )

    else:

        st.info(
            "Click 'Scan Now' to start scanning."
        )


# ============================================================
# TRADINGVIEW — RIGHT 65%
# ============================================================

with chart_col:

    st.markdown(
        "### TradingView"
    )

    selected = (
        st.session_state.get(
            "selected_ticker",
            "AAPL"
        )
    )

    # --------------------------------------------------------
    # EXCHANGE MAPPING
    # --------------------------------------------------------

    nyse_symbols = {
        "GME",
        "AMC",
        "BB",
        "OPEN"
    }

    if selected in nyse_symbols:

        tv_symbol = (
            f"NYSE:{selected}"
        )

    else:

        tv_symbol = (
            f"NASDAQ:{selected}"
        )

    # ========================================================
    # SQUARE TRADINGVIEW CONTAINER
    # ========================================================

    tradingview_html = f"""

    <style>

        html,
        body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
        }}

        .tv-square {{
            width: 100%;
            aspect-ratio: 1 / 1;
            position: relative;
            overflow: hidden;
        }}

        .tradingview-widget-container {{
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
        }}

        .tradingview-widget-container__widget {{
            width: 100%;
            height: calc(100% - 32px);
        }}

        .tradingview-widget-copyright {{
            width: 100%;
            height: 32px;
            line-height: 32px;
        }}

    </style>


    <div class="tv-square">

        <div
            class="tradingview-widget-container"
        >

            <div
                class="tradingview-widget-container__widget"
            ></div>

            <div
                class="tradingview-widget-copyright"
            >

                <a
                    href="https://www.tradingview.com/"
                    rel="noopener nofollow"
                    target="_blank"
                >
                    TradingView
                </a>

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

                "timezone":
                    "America/New_York",

                "theme": "dark",

                "style": "1",

                "locale": "en",

                "enable_publishing": false,

                "allow_symbol_change": true,

                "hide_top_toolbar": false,

                "hide_side_toolbar": false,

                "withdateranges": true,

                "hide_volume": false,

                "save_image": true,

                "studies": [],

                "show_popup_button": true,

                "popup_width": "1000",

                "popup_height": "850",

                "calendar": false,

                "details": false,

                "hotlist": false,

                "support_host":
                    "https://www.tradingview.com"
            }}

            </script>

        </div>

    </div>

    """

    # ========================================================
    # STREAMLIT HTML FRAME
    # ========================================================

    components.html(
        tradingview_html,
        height=900,
        scrolling=False
    )
