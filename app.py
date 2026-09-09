```python
import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="US Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# SETTINGS
# ============================================================

SETTINGS_FILE = "scanner_settings.json"

NY_TZ = ZoneInfo("America/New_York")

DEFAULT_SETTINGS = {
    "min_price": 1.0,
    "max_price": 20.0,
    "min_volume": 100000,
    "min_rvol": 2.0,
    "min_change": 2.0,
    "repeat_tolerance": 0.90,
    "refresh_seconds": 60,
    "auto_scan": False,
}


# ============================================================
# 30 STOCKS
# ============================================================
#
# These replace the Russell 2000 universe.
# You can change this list later.
#

STOCKS = [
    "AAPL",
    "AMD",
    "AMZN",
    "BAC",
    "COIN",
    "F",
    "HOOD",
    "INTC",
    "IONQ",
    "MARA",
    "META",
    "MSTR",
    "MU",
    "NFLX",
    "NIO",
    "NVDA",
    "ORCL",
    "PLTR",
    "PYPL",
    "RBLX",
    "RIVN",
    "SMCI",
    "SNAP",
    "SOFI",
    "T",
    "TSLA",
    "UBER",
    "WBD",
    "WFC",
    "XOM",
]


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    /* ------------------------------
       Overall page
       ------------------------------ */

    .stApp {
        background: #0b0f14;
        color: #e6edf3;
    }

    .block-container {
        padding-top: 0.6rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
        padding-bottom: 0.4rem;
        max-width: 100%;
    }


    /* ------------------------------
       Top header
       ------------------------------ */

    .top-header {
        height: 45px;
        display: flex;
        align-items: center;
        justify-content: space-between;

        border-bottom: 1px solid #252c35;

        margin-bottom: 8px;
    }

    .app-title {
        font-size: 19px;
        font-weight: 700;
        color: #f0f3f6;
    }

    .app-title-blue {
        color: #58a6ff;
    }

    .market-open {
        color: #3fb950;
        font-size: 11px;
        font-weight: 600;
    }

    .market-closed {
        color: #6e7681;
        font-size: 11px;
        font-weight: 600;
    }


    /* ------------------------------
       Panel
       ------------------------------ */

    .panel {
        background: #0f141a;
        border: 1px solid #252c35;
        border-radius: 5px;
    }

    .panel-header {
        height: 42px;

        display: flex;
        align-items: center;
        justify-content: space-between;

        padding-left: 11px;
        padding-right: 11px;

        border-bottom: 1px solid #252c35;
    }

    .panel-title {
        color: #dce3ea;
        font-size: 13px;
        font-weight: 700;
    }

    .panel-subtitle {
        color: #6e7681;
        font-size: 10px;
    }


    /* ------------------------------
       Scanner header
       ------------------------------ */

    .scanner-header {
        color: #6e7681;

        font-size: 9px;
        font-weight: 600;

        text-transform: uppercase;

        padding-top: 7px;
        padding-bottom: 7px;
        padding-left: 8px;
        padding-right: 8px;

        border-bottom: 1px solid #20262e;
    }


    /* ------------------------------
       Scanner row
       ------------------------------ */

    .scanner-row {
        min-height: 38px;

        border-bottom: 1px solid #181e25;

        display: flex;
        align-items: center;
    }

    .scanner-row:hover {
        background: #131920;
    }


    /* ------------------------------
       Text
       ------------------------------ */

    .time-text {
        color: #69737e;
        font-size: 10px;
    }

    .price-text {
        color: #dce3ea;
        font-size: 12px;
    }

    .positive-text {
        color: #3fb950;
        font-size: 12px;
        font-weight: 600;
    }

    .negative-text {
        color: #f85149;
        font-size: 12px;
        font-weight: 600;
    }

    .rvol-text {
        color: #58a6ff;
        font-size: 12px;
        font-weight: 600;
    }

    .repeat-dot {
        color: white;
        font-size: 10px;
        margin-right: 5px;
    }

    .no-repeat-dot {
        visibility: hidden;
        font-size: 10px;
        margin-right: 5px;
    }


    /* ------------------------------
       Ticker buttons
       ------------------------------ */

    div.stButton > button {
        background: transparent !important;

        border: none !important;

        color: #f0f3f6 !important;

        font-size: 12px !important;

        font-weight: 700 !important;

        padding: 0 !important;

        height: 34px !important;

        min-height: 34px !important;

        text-align: left !important;

        box-shadow: none !important;

        border-radius: 3px !important;
    }

    div.stButton > button:hover {
        background: #18212b !important;
        color: #58a6ff !important;
    }


    /* ------------------------------
       Empty scanner
       ------------------------------ */

    .empty-scanner {
        padding-top: 45px;
        padding-bottom: 45px;

        text-align: center;

        color: #6e7681;

        font-size: 12px;
    }

    .empty-title {
        color: #aab4bf;
        font-weight: 600;
        margin-bottom: 5px;
    }


    /* ------------------------------
       Sidebar
       ------------------------------ */

    section[data-testid="stSidebar"] {
        background: #0f141a;
        border-right: 1px solid #252c35;
    }


    /* ------------------------------
       Small status text
       ------------------------------ */

    .last-scan {
        color: #59636e;
        font-size: 9px;
        text-align: right;
        margin-top: 4px;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SETTINGS FUNCTIONS
# ============================================================

def load_settings():

    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()

    try:

        with open(SETTINGS_FILE, "r") as file:
            saved = json.load(file)

        settings = DEFAULT_SETTINGS.copy()
        settings.update(saved)

        return settings

    except Exception:

        return DEFAULT_SETTINGS.copy()


def save_settings(settings):

    try:

        with open(SETTINGS_FILE, "w") as file:
            json.dump(
                settings,
                file,
                indent=4
            )

    except Exception as error:

        st.error(
            f"Unable to save settings: {error}"
        )


# ============================================================
# SESSION STATE
# ============================================================

if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "NVDA"

if "scanner_data" not in st.session_state:
    st.session_state.scanner_data = pd.DataFrame()

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None


# ============================================================
# MARKET STATUS
# ============================================================

def market_is_open():

    now = datetime.now(NY_TZ)

    if now.weekday() >= 5:
        return False

    return (
        time(9, 30)
        <= now.time()
        <= time(16, 0)
    )


# ============================================================
# REPEAT VOLUME
# ============================================================

def detect_repeat(
    intraday,
    tolerance
):

    if intraday is None:
        return False

    if intraday.empty:
        return False

    if "Volume" not in intraday.columns:
        return False

    volumes = pd.to_numeric(
        intraday["Volume"],
        errors="coerce"
    ).dropna()

    if len(volumes) < 2:
        return False

    current_volume = float(
        volumes.iloc[-1]
    )

    previous_volumes = volumes.iloc[:-1]

    if previous_volumes.empty:
        return False

    highest_previous = float(
        previous_volumes.max()
    )

    if highest_previous <= 0:
        return False

    return (
        current_volume
        >= highest_previous * tolerance
    )


# ============================================================
# YAHOO DATA CLEANUP
# ============================================================

def clean_yahoo_data(
    data,
    symbol
):

    if data is None:
        return None

    if data.empty:
        return None

    try:

        if isinstance(
            data.columns,
            pd.MultiIndex
        ):

            # Try symbol level
            try:

                data = data.xs(
                    symbol,
                    axis=1,
                    level=1
                )

            except Exception:

                try:

                    data = data.xs(
                        symbol,
                        axis=1,
                        level=0
                    )

                except Exception:
                    pass

        data = data.dropna(
            how="all"
        )

        if data.empty:
            return None

        return data

    except Exception:

        return None


# ============================================================
# SCAN ALL 30 STOCKS
# ============================================================

def run_scanner():

    settings = st.session_state.settings

    symbols = STOCKS.copy()

    # --------------------------------------------------------
    # Download 1-minute data
    # --------------------------------------------------------

    progress = st.progress(0)

    status = st.empty()

    try:

        intraday = yf.download(
            tickers=symbols,
            period="1d",
            interval="1m",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )

    except Exception as error:

        progress.empty()
        status.empty()

        st.error(
            f"Could not download 1-minute data: {error}"
        )

        return pd.DataFrame()

    progress.progress(0.50)

    status.markdown(
        "**Downloading daily data...**"
    )

    # --------------------------------------------------------
    # Download daily data
    # --------------------------------------------------------

    try:

        daily = yf.download(
            tickers=symbols,
            period="20d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )

    except Exception:

        daily = None

    progress.progress(0.75)

    status.markdown(
        "**Processing stocks...**"
    )

    results = []

    # --------------------------------------------------------
    # Process each stock
    # --------------------------------------------------------

    for symbol in symbols:

        try:

            intraday_data = clean_yahoo_data(
                intraday,
                symbol
            )

            if (
                intraday_data is None
                or intraday_data.empty
            ):
                continue

            # -----------------------------------------------
            # Price
            # -----------------------------------------------

            close = pd.to_numeric(
                intraday_data["Close"],
                errors="coerce"
            ).dropna()

            if close.empty:
                continue

            ltp = float(
                close.iloc[-1]
            )

            if ltp <= 0:
                continue

            # -----------------------------------------------
            # Volume
            # -----------------------------------------------

            volume = pd.to_numeric(
                intraday_data["Volume"],
                errors="coerce"
            ).fillna(0)

            session_volume = int(
                volume.sum()
            )

            if session_volume <= 0:
                continue

            # -----------------------------------------------
            # Daily data
            # -----------------------------------------------

            previous_close = None
            average_volume = None

            daily_data = clean_yahoo_data(
                daily,
                symbol
            )

            if (
                daily_data is not None
                and not daily_data.empty
            ):

                daily_close = pd.to_numeric(
                    daily_data["Close"],
                    errors="coerce"
                ).dropna()

                daily_volume = pd.to_numeric(
                    daily_data["Volume"],
                    errors="coerce"
                ).dropna()

                if len(daily_close) >= 2:

                    previous_close = float(
                        daily_close.iloc[-2]
                    )

                if len(daily_volume) >= 6:

                    average_volume = float(
                        daily_volume.iloc[-6:-1].mean()
                    )

            if (
                previous_close is None
                or previous_close <= 0
            ):
                continue

            if (
                average_volume is None
                or average_volume <= 0
            ):
                continue

            # -----------------------------------------------
            # % Change
            # -----------------------------------------------

            percent_change = (
                (
                    ltp
                    - previous_close
                )
                / previous_close
            ) * 100

            # -----------------------------------------------
            # Relative volume
            # -----------------------------------------------

            relative_volume = (
                session_volume
                / average_volume
            )

            # -----------------------------------------------
            # Repeat
            # -----------------------------------------------

            repeat = detect_repeat(
                intraday_data,
                settings["repeat_tolerance"]
            )

            # -----------------------------------------------
            # Time
            # -----------------------------------------------

            latest_time = (
                intraday_data.index[-1]
            )

            try:

                if latest_time.tzinfo is None:

                    latest_time = latest_time.replace(
                        tzinfo=NY_TZ
                    )

                else:

                    latest_time = latest_time.astimezone(
                        NY_TZ
                    )

                time_text = (
                    latest_time.strftime(
                        "%H:%M"
                    )
                )

            except Exception:

                time_text = "--"

            # -----------------------------------------------
            # Store
            # -----------------------------------------------

            results.append(
                {
                    "Time": time_text,
                    "Symbol": symbol,
                    "LTP": round(
                        ltp,
                        2
                    ),
                    "% Change": round(
                        float(percent_change),
                        2
                    ),
                    "Rel Vol": round(
                        float(relative_volume),
                        1
                    ),
                    "Volume": session_volume,
                    "Repeat": repeat,
                }
            )

        except Exception:

            continue

    progress.progress(1.0)

    progress.empty()
    status.empty()

    if not results:

        return pd.DataFrame()

    df = pd.DataFrame(
        results
    )

    # ========================================================
    # FILTERS
    # ========================================================

    df = df[
        (df["LTP"] >= settings["min_price"])
        &
        (df["LTP"] <= settings["max_price"])
        &
        (df["Volume"] >= settings["min_volume"])
        &
        (df["Rel Vol"] >= settings["min_rvol"])
        &
        (df["% Change"] >= settings["min_change"])
    ]

    # ========================================================
    # SORT
    # ========================================================

    df = df.sort_values(
        by=[
            "Repeat",
            "Rel Vol",
            "% Change",
        ],
        ascending=[
            False,
            False,
            False,
        ]
    )

    return df.reset_index(
        drop=True
    )


# ============================================================
# TRADINGVIEW
# ============================================================

def tradingview_chart(symbol):

    from streamlit.components.v1 import html

    tv_symbol = f"NASDAQ:{symbol}"

    chart = f"""
    <!DOCTYPE html>

    <html>

    <head>

        <style>

            html,
            body {{
                margin: 0;
                padding: 0;

                width: 100%;
                height: 100%;

                overflow: hidden;

                background: #0b0f14;
            }}

            #tradingview {{
                width: 100%;
                height: 100%;
            }}

        </style>

    </head>

    <body>

        <div id="tradingview"></div>

        <script
            src="https://s3.tradingview.com/tv.js">
        </script>

        <script>

            new TradingView.widget({{

                autosize: true,

                symbol: "{tv_symbol}",

                interval: "1",

                timezone:
                    "America/New_York",

                theme: "dark",

                style: "1",

                locale: "en",

                enable_publishing: false,

                allow_symbol_change: true,

                hide_side_toolbar: false,

                hide_top_toolbar: false,

                withdateranges: true,

                save_image: false,

                container_id:
                    "tradingview"

            }});

        </script>

    </body>

    </html>
    """

    html(
        chart,
        height=820,
        scrolling=False
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## ⚙ Filters"
    )

    st.markdown("---")

    settings = st.session_state.settings

    auto_scan = st.checkbox(
        "Automatic Scanner",
        value=bool(
            settings["auto_scan"]
        )
    )

    refresh_seconds = st.number_input(
        "Refresh seconds",
        min_value=10,
        max_value=3600,
        value=int(
            settings["refresh_seconds"]
        ),
        step=10
    )

    st.markdown("---")

    st.markdown(
        "#### Price"
    )

    min_price = st.number_input(
        "Minimum price",
        min_value=0.01,
        max_value=10000.0,
        value=float(
            settings["min_price"]
        ),
        step=0.50
    )

    max_price = st.number_input(
        "Maximum price",
        min_value=0.01,
        max_value=10000.0,
        value=float(
            settings["max_price"]
        ),
        step=0.50
    )

    st.markdown(
        "#### Volume"
    )

    min_volume = st.number_input(
        "Minimum volume",
        min_value=0,
        max_value=1000000000,
        value=int(
            settings["min_volume"]
        ),
        step=100000
    )

    min_rvol = st.number_input(
        "Minimum Rel Vol",
        min_value=0.1,
        max_value=1000.0,
        value=float(
            settings["min_rvol"]
        ),
        step=0.5
    )

    min_change = st.number_input(
        "Minimum % Change",
        min_value=-100.0,
        max_value=1000.0,
        value=float(
            settings["min_change"]
        ),
        step=0.5
    )

    st.markdown(
        "#### Repeat Volume"
    )

    repeat_percent = st.slider(
        "Repeat tolerance",
        min_value=50,
        max_value=100,
        value=int(
            settings["repeat_tolerance"]
            * 100
        ),
        step=1
    )

    st.caption(
        "90% means the current 1-minute "
        "volume must reach at least 90% "
        "of the previous highest 1-minute volume."
    )

    st.markdown("---")

    save_button = st.button(
        "💾 Save Settings",
        use_container_width=True
    )

    scan_button = st.button(
        "🔎 Scan Now",
        type="primary",
        use_container_width=True
    )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    if save_button:

        st.session_state.settings = {
            "min_price": min_price,
            "max_price": max_price,
            "min_volume": min_volume,
            "min_rvol": min_rvol,
            "min_change": min_change,
            "repeat_tolerance":
                repeat_percent / 100,
            "refresh_seconds":
                refresh_seconds,
            "auto_scan":
                auto_scan,
        }

        save_settings(
            st.session_state.settings
        )

        st.success(
            "Settings saved."
        )

    # --------------------------------------------------------
    # SCAN
    # --------------------------------------------------------

    if scan_button:

        st.session_state.settings = {
            "min_price": min_price,
            "max_price": max_price,
            "min_volume": min_volume,
            "min_rvol": min_rvol,
            "min_change": min_change,
            "repeat_tolerance":
                repeat_percent / 100,
            "refresh_seconds":
                refresh_seconds,
            "auto_scan":
                auto_scan,
        }

        save_settings(
            st.session_state.settings
        )

        result = run_scanner()

        st.session_state.scanner_data = result

        st.session_state.last_scan = (
            datetime.now(NY_TZ)
        )

        if result.empty:

            st.warning(
                "No stocks match your filters."
            )

        else:

            st.success(
                f"{len(result)} stocks found."
            )


# ============================================================
# TOP HEADER
# ============================================================

if market_is_open():

    market_html = (
        '<span class="market-open">'
        '● US MARKET OPEN'
        '</span>'
    )

else:

    market_html = (
        '<span class="market-closed">'
        '● US MARKET CLOSED'
        '</span>'
    )


st.markdown(
    f"""
    <div class="top-header">

        <div class="app-title">
            📈
            <span class="app-title-blue">
                US Momentum
            </span>
            Scanner
        </div>

        <div>
            {market_html}
        </div>

    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# MAIN LAYOUT
# ============================================================

scanner_column, chart_column = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT SCANNER
# ============================================================

with scanner_column:

    data = st.session_state.scanner_data

    count = (
        len(data)
        if not data.empty
        else 0
    )

    # --------------------------------------------------------
    # Panel header
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="panel">

            <div class="panel-header">

                <div class="panel-title">
                    Momentum Scanner
                </div>

                <div class="panel-subtitle">
                    {count} results
                </div>

            </div>

            <div class="scanner-header">

                <div style="
                    display:grid;
                    grid-template-columns:
                    55px
                    1fr
                    72px
                    82px
                    65px;
                ">

                    <div>Time</div>
                    <div>Symbol</div>
                    <div>LTP</div>
                    <div>Change</div>
                    <div>Rel Vol</div>

                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # Empty scanner
    # --------------------------------------------------------

    if data.empty:

        st.markdown(
            """
            <div class="empty-scanner">

                <div class="empty-title">
                    Scanner ready
                </div>

                Open
                <b>⚙ Filters</b>
                and click
                <b>Scan Now</b>.

            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # Stock rows
    # --------------------------------------------------------

    else:

        for index, row in data.iterrows():

            symbol = str(
                row["Symbol"]
            )

            # ------------------------------------------------
            # Five columns
            # ------------------------------------------------

            col_time, col_symbol, col_ltp, col_change, col_rvol = st.columns(
                [
                    0.65,
                    1.45,
                    0.85,
                    0.95,
                    0.75
                ],
                gap="small"
            )

            # ------------------------------------------------
            # Time
            # ------------------------------------------------

            with col_time:

                st.markdown(
                    f"""
                    <div class="scanner-row">
                        <span class="time-text">
                            {row["Time"]}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # ------------------------------------------------
            # Symbol
            # ------------------------------------------------

            with col_symbol:

                repeat = bool(
                    row["Repeat"]
                )

                if repeat:

                    dot = (
                        '<span class="repeat-dot">'
                        '●'
                        '</span>'
                    )

                else:

                    dot = (
                        '<span class="no-repeat-dot">'
                        '●'
                        '</span>'
                    )

                # Button itself
                clicked = st.button(
                    symbol,
                    key=f"symbol_{symbol}_{index}",
                    use_container_width=True
                )

                # Dot beside ticker
                st.markdown(
                    f"""
                    <div style="
                        margin-top:-34px;
                        height:34px;
                        display:flex;
                        align-items:center;
                        pointer-events:none;
                    ">

                        {dot}

                    </div>
                    """,
                    unsafe_allow_html=True
                )

                if clicked:

                    st.session_state.selected_ticker = (
                        symbol
                    )

                    st.rerun()

            # ------------------------------------------------
            # LTP
            # ------------------------------------------------

            with col_ltp:

                st.markdown(
                    f"""
                    <div class="scanner-row">
                        <span class="price-text">
                            ${float(row["LTP"]):.2f}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # ------------------------------------------------
            # Change
            # ------------------------------------------------

            with col_change:

                change = float(
                    row["% Change"]
                )

                if change >= 0:

                    change_class = (
                        "positive-text"
                    )

                else:

                    change_class = (
                        "negative-text"
                    )

                st.markdown(
                    f"""
                    <div class="scanner-row">
                        <span class="{change_class}">
                            {change:+.2f}%
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            # ------------------------------------------------
            # Relative volume
            # ------------------------------------------------

            with col_rvol:

                st.markdown(
                    f"""
                    <div class="scanner-row">
                        <span class="rvol-text">
                            {float(row["Rel Vol"]):.1f}
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


# ============================================================
# RIGHT TRADINGVIEW
# ============================================================

with chart_column:

    selected = (
        st.session_state.selected_ticker
    )

    st.markdown(
        f"""
        <div class="panel">

            <div class="panel-header">

                <div class="panel-title">

                    TradingView

                    <span style="
                        color:#58a6ff;
                        margin-left:6px;
                    ">
                        {selected}
                    </span>

                </div>

                <div class="panel-subtitle">
                    1 MIN
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    tradingview_chart(
        selected
    )


# ============================================================
# LAST SCAN
# ============================================================

if st.session_state.last_scan:

    last_scan = (
        st.session_state.last_scan.strftime(
            "%H:%M:%S"
        )
    )

else:

    last_scan = "--"

st.markdown(
    f"""
    <div class="last-scan">
        30-stock universe
        &nbsp; | &nbsp;
        Last scan: {last_scan}
    </div>
    """,
    unsafe_allow_html=True
)
```
