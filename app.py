import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import io
import os
import json

from datetime import datetime, time
from zoneinfo import ZoneInfo


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="US Momentum Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    /* --------------------------------------------------------
       MAIN PAGE
    -------------------------------------------------------- */

    .block-container {
        max-width: 100% !important;
        width: 100% !important;

        padding-top: 0.35rem !important;
        padding-bottom: 0.2rem !important;
        padding-left: 0.35rem !important;
        padding-right: 0.35rem !important;
    }

    .main-title {
        font-size: 22px;
        font-weight: 800;
        margin-bottom: 0px;
        line-height: 1.1;
    }

    .sub-title {
        font-size: 11px;
        opacity: 0.65;
        margin-bottom: 4px;
    }


    /* --------------------------------------------------------
       SCANNER
    -------------------------------------------------------- */

    .scanner-header {
        font-size: 10px;
        font-weight: 800;

        padding-top: 3px;
        padding-bottom: 3px;
        padding-left: 1px;
        padding-right: 1px;

        white-space: nowrap;
        overflow: hidden;
    }

    .scanner-row {
        font-size: 10px;

        padding-top: 2px;
        padding-bottom: 2px;
        padding-left: 1px;
        padding-right: 1px;

        white-space: nowrap;
        overflow: hidden;
        text-overflow: clip;

        border-bottom: 1px solid rgba(128,128,128,0.12);
    }


    /* --------------------------------------------------------
       TICKER BUTTON
    -------------------------------------------------------- */

    div.stButton > button {

        min-height: 24px !important;

        height: 24px !important;

        padding-top: 0px !important;
        padding-bottom: 0px !important;
        padding-left: 1px !important;
        padding-right: 1px !important;

        font-size: 10px !important;
        font-weight: 700 !important;

        white-space: nowrap !important;

        overflow: hidden !important;
        text-overflow: clip !important;
    }


    /* --------------------------------------------------------
       REPEAT SIGNAL
    -------------------------------------------------------- */

    .repeat-square {

        font-size: 18px;

        font-weight: 900;

        line-height: 1;

        color: white;

        margin-top: 1px;

        margin-left: 0px;
    }


    /* --------------------------------------------------------
       TRADINGVIEW
    -------------------------------------------------------- */

    .tradingview-container {

        width: 100%;

        min-width: 0;

        overflow: hidden;
    }


    /* --------------------------------------------------------
       SIDEBAR
    -------------------------------------------------------- */

    section[data-testid="stSidebar"] {

        min-width: 260px !important;
        max-width: 280px !important;
    }


    /* --------------------------------------------------------
       REDUCE STREAMLIT GAPS
    -------------------------------------------------------- */

    div[data-testid="stVerticalBlock"] {

        gap: 0.12rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SETTINGS
# ============================================================

SETTINGS_FILE = "scanner_settings.json"

DEFAULT_SETTINGS = {

    "min_price": 1.0,

    "max_price": 20.0,

    "min_volume": 100000,

    "min_rvol": 2.0,

    "min_change": 2.0,

    "max_stocks": 300,

    "repeat_tolerance": 0.90,

    "refresh_seconds": 60,

    "auto_scan": True,
}


NY_TZ = ZoneInfo(
    "America/New_York"
)


# ============================================================
# LOAD SETTINGS
# ============================================================

def load_settings():

    if os.path.exists(
        SETTINGS_FILE
    ):

        try:

            with open(
                SETTINGS_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                saved = json.load(f)

            settings = (
                DEFAULT_SETTINGS.copy()
            )

            settings.update(
                saved
            )

            return settings

        except Exception:

            pass

    return (
        DEFAULT_SETTINGS.copy()
    )


# ============================================================
# SAVE SETTINGS
# ============================================================

def save_settings(
    settings
):

    try:

        with open(
            SETTINGS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                settings,
                f,
                indent=4
            )

        return True

    except Exception:

        return False


# ============================================================
# SESSION STATE
# ============================================================

if "settings" not in st.session_state:

    st.session_state.settings = (
        load_settings()
    )


if "selected_ticker" not in st.session_state:

    st.session_state.selected_ticker = (
        "AAPL"
    )


if "scanner_data" not in st.session_state:

    st.session_state.scanner_data = (
        pd.DataFrame()
    )


if "last_scan" not in st.session_state:

    st.session_state.last_scan = None


# ============================================================
# MARKET HOURS
# ============================================================

def market_is_open():

    now = datetime.now(
        NY_TZ
    )

    if now.weekday() >= 5:

        return False

    market_open = time(
        9,
        30
    )

    market_close = time(
        16,
        0
    )

    return (
        market_open
        <= now.time()
        <= market_close
    )


# ============================================================
# RUSSELL 2000
# ============================================================

@st.cache_data(
    ttl=3600,
    show_spinner=False
)
def load_russell_2000():

    url = (
        "https://www.ishares.com/us/products/"
        "239710/ishares-russell-2000-etf/"
        "latest-holdings.csv"
    )

    try:

        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent":
                "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        lines = (
            response.text.splitlines()
        )

        header_index = None

        for i, line in enumerate(
            lines
        ):

            if line.startswith(
                "Ticker,Name"
            ):

                header_index = i

                break

        if header_index is None:

            raise ValueError(
                "Russell 2000 CSV header not found."
            )

        csv_text = "\n".join(
            lines[header_index:]
        )

        df = pd.read_csv(
            io.StringIO(
                csv_text
            )
        )

        if "Asset Class" in df.columns:

            df = df[
                df[
                    "Asset Class"
                ]
                .astype(str)
                .str.lower()
                .eq("equity")
            ]

        if "Location" in df.columns:

            df = df[
                df[
                    "Location"
                ]
                .astype(str)
                .str.contains(
                    "United States",
                    case=False,
                    na=False
                )
            ]

        df["Ticker"] = (

            df["Ticker"]

            .astype(str)

            .str.strip()

            .str.upper()

            .str.replace(
                ".",
                "-",
                regex=False
            )
        )

        invalid = [
            "",
            "NAN",
            "USD",
            "CASH",
            "N/A",
        ]

        df = df[
            ~df["Ticker"].isin(
                invalid
            )
        ]

        return (
            df["Ticker"]
            .drop_duplicates()
            .tolist()
        )

    except Exception as e:

        st.warning(
            f"Unable to load Russell 2000: {e}"
        )

        return []


# ============================================================
# GET SYMBOL DATA
# ============================================================

def get_symbol_data(
    data,
    symbol
):

    if (
        data is None
        or data.empty
    ):

        return None

    try:

        if isinstance(
            data.columns,
            pd.MultiIndex
        ):

            if (
                symbol
                in data.columns
                .get_level_values(0)
            ):

                result = data[
                    symbol
                ].copy()

            elif (
                symbol
                in data.columns
                .get_level_values(1)
            ):

                result = data.xs(
                    symbol,
                    axis=1,
                    level=1
                ).copy()

            else:

                return None

        else:

            result = data.copy()

        return result.dropna(
            how="all"
        )

    except Exception:

        return None


# ============================================================
# REPEAT VOLUME
# ============================================================

def detect_repeat(
    session_data,
    tolerance=0.90
):

    if (
        session_data is None
        or session_data.empty
    ):

        return False, 0, 0

    if (
        "Volume"
        not in session_data.columns
    ):

        return False, 0, 0

    volumes = pd.to_numeric(
        session_data["Volume"],
        errors="coerce"
    ).dropna()

    volumes = volumes[
        volumes > 0
    ]

    if len(volumes) < 2:

        return False, 0, 0

    current_volume = float(
        volumes.iloc[-1]
    )

    previous_volumes = (
        volumes.iloc[:-1]
    )

    previous_highest = float(
        previous_volumes.max()
    )

    if previous_highest <= 0:

        return (
            False,
            current_volume,
            previous_highest
        )

    repeat = (
        current_volume
        >=
        previous_highest
        * tolerance
    )

    return (
        repeat,
        current_volume,
        previous_highest
    )


# ============================================================
# SCAN BATCH
# ============================================================

def scan_batch(
    symbols
):

    if not symbols:

        return pd.DataFrame()

    results = []

    # --------------------------------------------------------
    # 1 MINUTE DATA
    # --------------------------------------------------------

    try:

        intraday = yf.download(
            tickers=symbols,
            period="1d",
            interval="1m",
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            threads=True,
            progress=False,
        )

    except Exception:

        intraday = pd.DataFrame()


    # --------------------------------------------------------
    # DAILY DATA
    # --------------------------------------------------------

    try:

        daily = yf.download(
            tickers=symbols,
            period="20d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            threads=True,
            progress=False,
        )

    except Exception:

        daily = pd.DataFrame()


    # --------------------------------------------------------
    # PROCESS STOCKS
    # --------------------------------------------------------

    for symbol in symbols:

        try:

            minute_data = (
                get_symbol_data(
                    intraday,
                    symbol
                )
            )

            daily_data = (
                get_symbol_data(
                    daily,
                    symbol
                )
            )

            if (
                minute_data is None
                or minute_data.empty
            ):

                continue

            required = [
                "Close",
                "Volume"
            ]

            if not all(
                col in minute_data.columns
                for col in required
            ):

                continue

            minute_data = (
                minute_data.dropna(
                    subset=["Close"]
                )
            )

            if minute_data.empty:

                continue

            ltp = float(
                minute_data[
                    "Close"
                ].iloc[-1]
            )

            if ltp <= 0:

                continue

            latest_date = (
                minute_data
                .index[-1]
                .date()
            )

            session_data = (
                minute_data[
                    minute_data.index.date
                    == latest_date
                ]
                .copy()
            )

            if session_data.empty:

                continue

            session_volume = float(
                pd.to_numeric(
                    session_data[
                        "Volume"
                    ],
                    errors="coerce"
                )
                .fillna(0)
                .sum()
            )

            (
                repeat,
                current_volume,
                previous_spike
            ) = detect_repeat(
                session_data,
                st.session_state.settings[
                    "repeat_tolerance"
                ]
            )

            # ------------------------------------------------
            # PREVIOUS CLOSE
            # ------------------------------------------------

            previous_close = np.nan

            if (
                daily_data is not None
                and not daily_data.empty
                and "Close"
                in daily_data.columns
            ):

                closes = pd.to_numeric(
                    daily_data[
                        "Close"
                    ],
                    errors="coerce"
                ).dropna()

                if len(closes) >= 2:

                    previous_close = float(
                        closes.iloc[-2]
                    )

            if (
                pd.isna(previous_close)
                or previous_close <= 0
            ):

                continue

            # ------------------------------------------------
            # % CHANGE
            # ------------------------------------------------

            percent_change = (
                (
                    ltp
                    - previous_close
                )
                / previous_close
                * 100
            )

            # ------------------------------------------------
            # AVERAGE DAILY VOLUME
            # ------------------------------------------------

            avg_volume = np.nan

            if (
                daily_data is not None
                and not daily_data.empty
                and "Volume"
                in daily_data.columns
            ):

                daily_volumes = (
                    pd.to_numeric(
                        daily_data[
                            "Volume"
                        ],
                        errors="coerce"
                    )
                    .dropna()
                )

                if len(
                    daily_volumes
                ) >= 2:

                    avg_volume = float(
                        daily_volumes
                        .iloc[:-1]
                        .tail(5)
                        .mean()
                    )

            # ------------------------------------------------
            # RELATIVE VOLUME
            # ------------------------------------------------

            if (
                pd.isna(avg_volume)
                or avg_volume <= 0
            ):

                rel_volume = 0.0

            else:

                rel_volume = (
                    session_volume
                    / avg_volume
                )

            results.append(
                {
                    "Time":
                        session_data
                        .index[-1],

                    "Symbol":
                        symbol,

                    "LTP":
                        ltp,

                    "% Change":
                        percent_change,

                    "Rel Vol":
                        rel_volume,

                    "Volume":
                        session_volume,

                    "Repeat":
                        bool(repeat),
                }
            )

        except Exception:

            continue

    if not results:

        return pd.DataFrame()

    return pd.DataFrame(
        results
    )


# ============================================================
# RUN SCANNER
# ============================================================

def run_scanner():

    settings = (
        st.session_state.settings
    )

    symbols = (
        load_russell_2000()
    )

    max_stocks = int(
        settings[
            "max_stocks"
        ]
    )

    symbols = symbols[
        :max_stocks
    ]

    if not symbols:

        return pd.DataFrame()

    all_results = []

    batch_size = 50

    for start in range(
        0,
        len(symbols),
        batch_size
    ):

        batch = symbols[
            start:
            start + batch_size
        ]

        result = scan_batch(
            batch
        )

        if (
            result is not None
            and not result.empty
        ):

            all_results.append(
                result
            )

    if not all_results:

        return pd.DataFrame()

    result = pd.concat(
        all_results,
        ignore_index=True
    )

    # --------------------------------------------------------
    # FILTERS
    # --------------------------------------------------------

    result = result[
        (
            result["LTP"]
            >= settings["min_price"]
        )
        &
        (
            result["LTP"]
            <= settings["max_price"]
        )
        &
        (
            result["Volume"]
            >= settings["min_volume"]
        )
        &
        (
            result["Rel Vol"]
            >= settings["min_rvol"]
        )
        &
        (
            result["% Change"]
            >= settings["min_change"]
        )
    ].copy()

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    result = result.sort_values(
        by=[
            "Repeat",
            "Rel Vol",
            "% Change"
        ],
        ascending=[
            False,
            False,
            False
        ]
    )

    return result.reset_index(
        drop=True
    )


# ============================================================
# TRADINGVIEW
# ============================================================

def tradingview_chart(
    symbol,
    height=620
):

    import streamlit.components.v1 as components

    tv_symbol = (
        f"NASDAQ:{symbol}"
    )

    html = f"""
    <div
        class="tradingview-container"
        style="
            width:100%;
            height:{height}px;
        "
    >

        <div
            class="tradingview-widget-container"
            style="
                width:100%;
                height:100%;
            "
        >

            <div
                class="tradingview-widget-container__widget"
                style="
                    width:100%;
                    height:100%;
                "
            ></div>

            <script
                type="text/javascript"
                src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
                async
            >
            {{
                "autosize": true,

                "symbol": "{tv_symbol}",

                "interval": "1",

                "timezone": "America/New_York",

                "theme": "dark",

                "style": "1",

                "withdateranges": true,

                "hide_side_toolbar": false,

                "allow_symbol_change": true,

                "save_image": true,

                "hide_volume": false,

                "hide_legend": false,

                "calendar": false,

                "studies": [],

                "locale": "en",

                "support_host":
                    "https://www.tradingview.com"
            }}
            </script>

        </div>

    </div>
    """

    components.html(
        html,
        height=height,
        scrolling=False
    )


# ============================================================
# TITLE
# ============================================================

st.markdown(
    """
    <div class="main-title">
        📈 US Momentum Stock Scanner
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="sub-title">
        1-minute momentum scanner • Russell 2000 • TradingView
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "Scanner Settings"
    )

    auto_scan = st.checkbox(
        "Automatic Scanner",
        value=st.session_state.settings[
            "auto_scan"
        ]
    )

    refresh_options = [
        30,
        60,
        90,
        120,
        180,
        300
    ]

    current_refresh = int(
        st.session_state.settings[
            "refresh_seconds"
        ]
    )

    if (
        current_refresh
        not in refresh_options
    ):

        current_refresh = 60

    refresh_seconds = st.selectbox(
        "Refresh interval",
        refresh_options,
        index=refresh_options.index(
            current_refresh
        )
    )

    st.divider()

    min_price = st.number_input(
        "Minimum price",
        min_value=0.01,
        value=float(
            st.session_state.settings[
                "min_price"
            ]
        ),
        step=0.50
    )

    max_price = st.number_input(
        "Maximum price",
        min_value=0.01,
        value=float(
            st.session_state.settings[
                "max_price"
            ]
        ),
        step=0.50
    )

    min_volume = st.number_input(
        "Minimum volume",
        min_value=0,
        value=int(
            st.session_state.settings[
                "min_volume"
            ]
        ),
        step=100000
    )

    min_rvol = st.number_input(
        "Minimum Rel Vol",
        min_value=0.0,
        value=float(
            st.session_state.settings[
                "min_rvol"
            ]
        ),
        step=0.5
    )

    min_change = st.number_input(
        "Minimum % Change",
        value=float(
            st.session_state.settings[
                "min_change"
            ]
        ),
        step=0.5
    )

    max_stocks = st.number_input(
        "Maximum stocks to scan",
        min_value=10,
        max_value=2000,
        value=int(
            st.session_state.settings[
                "max_stocks"
            ]
        ),
        step=50
    )

    repeat_percent = st.slider(
        "Repeat volume threshold",
        min_value=50,
        max_value=100,
        value=int(
            st.session_state.settings[
                "repeat_tolerance"
            ] * 100
        ),
        step=5
    )

    st.divider()

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    if st.button(
        "💾 Save Settings",
        use_container_width=True
    ):

        st.session_state.settings = {

            "min_price":
                float(min_price),

            "max_price":
                float(max_price),

            "min_volume":
                int(min_volume),

            "min_rvol":
                float(min_rvol),

            "min_change":
                float(min_change),

            "max_stocks":
                int(max_stocks),

            "repeat_tolerance":
                float(
                    repeat_percent
                    / 100
                ),

            "refresh_seconds":
                int(refresh_seconds),

            "auto_scan":
                bool(auto_scan),
        }

        save_settings(
            st.session_state.settings
        )

        st.success(
            "Settings saved"
        )

    # --------------------------------------------------------
    # SCAN NOW
    # --------------------------------------------------------

    if st.button(
        "🔎 Scan Now",
        use_container_width=True
    ):

        st.session_state.settings = {

            "min_price":
                float(min_price),

            "max_price":
                float(max_price),

            "min_volume":
                int(min_volume),

            "min_rvol":
                float(min_rvol),

            "min_change":
                float(min_change),

            "max_stocks":
                int(max_stocks),

            "repeat_tolerance":
                float(
                    repeat_percent
                    / 100
                ),

            "refresh_seconds":
                int(refresh_seconds),

            "auto_scan":
                bool(auto_scan),
        }

        with st.spinner(
            "Scanning stocks..."
        ):

            st.session_state.scanner_data = (
                run_scanner()
            )

        st.session_state.last_scan = (
            datetime.now()
        )

        st.rerun()


# ============================================================
# AUTO REFRESH
# ============================================================

run_every = None

if (
    st.session_state.settings[
        "auto_scan"
    ]
    and market_is_open()
):

    run_every = (
        f'{st.session_state.settings["refresh_seconds"]}s'
    )


# ============================================================
# MAIN DISPLAY
# ============================================================

@st.fragment(
    run_every=run_every
)
def automatic_scanner():

    # --------------------------------------------------------
    # AUTOMATIC UPDATE
    # --------------------------------------------------------

    if (
        st.session_state.settings[
            "auto_scan"
        ]
        and market_is_open()
    ):

        with st.spinner(
            "Updating scanner..."
        ):

            st.session_state.scanner_data = (
                run_scanner()
            )

        st.session_state.last_scan = (
            datetime.now()
        )

    data = (
        st.session_state.scanner_data
    )


    # ========================================================
    # MAIN LAYOUT
    #
    # SCANNER = 20%
    # CHART   = 80%
    # ========================================================

    left_col, right_col = st.columns(
        [1, 4],
        gap="small"
    )


    # ========================================================
    # LEFT SCANNER
    # ========================================================

    with left_col:

        st.markdown(
            "### Scanner"
        )

        if (
            st.session_state.last_scan
            is not None
        ):

            st.caption(
                "Updated "
                +
                st.session_state.last_scan.strftime(
                    "%H:%M:%S"
                )
            )

        if (
            data is None
            or data.empty
        ):

            st.info(
                "No stocks match your filters."
            )

        else:

            # ------------------------------------------------
            # HEADER
            # ------------------------------------------------

            header_cols = st.columns(
                [
                    0.65,
                    1.10,
                    0.65,
                    0.85,
                    0.60
                ],
                gap="small"
            )

            header_cols[0].markdown(
                '<div class="scanner-header">Time</div>',
                unsafe_allow_html=True
            )

            header_cols[1].markdown(
                '<div class="scanner-header">Symbol</div>',
                unsafe_allow_html=True
            )

            header_cols[2].markdown(
                '<div class="scanner-header">LTP</div>',
                unsafe_allow_html=True
            )

            header_cols[3].markdown(
                '<div class="scanner-header">% Chg</div>',
                unsafe_allow_html=True
            )

            header_cols[4].markdown(
                '<div class="scanner-header">RVOL</div>',
                unsafe_allow_html=True
            )


            # ------------------------------------------------
            # ROWS
            # ------------------------------------------------

            for _, row in data.iterrows():

                row_cols = st.columns(
                    [
                        0.65,
                        1.10,
                        0.65,
                        0.85,
                        0.60
                    ],
                    gap="small"
                )

                # --------------------------------------------
                # TIME
                # --------------------------------------------

                try:

                    row_time = (
                        pd.to_datetime(
                            row["Time"]
                        )
                        .strftime(
                            "%H:%M"
                        )
                    )

                except Exception:

                    row_time = "--"

                row_cols[0].markdown(
                    f"""
                    <div class="scanner-row">
                        {row_time}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


                # --------------------------------------------
                # SYMBOL
                # --------------------------------------------

                ticker = str(
                    row["Symbol"]
                )

                symbol_cols = (
                    row_cols[1].columns(
                        [1.0, 0.22],
                        gap="small"
                    )
                )

                if symbol_cols[0].button(
                    ticker,
                    key=(
                        f"ticker_"
                        f"{ticker}_"
                        f"{row['Time']}"
                    ),
                    use_container_width=True
                ):

                    st.session_state.selected_ticker = (
                        ticker
                    )

                    st.rerun()


                # --------------------------------------------
                # REPEAT ■
                # --------------------------------------------

                if bool(
                    row["Repeat"]
                ):

                    symbol_cols[1].markdown(
                        """
                        <div class="repeat-square">
                            ■
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


                # --------------------------------------------
                # LTP
                # --------------------------------------------

                row_cols[2].markdown(
                    f"""
                    <div class="scanner-row">
                        ${row["LTP"]:.2f}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


                # --------------------------------------------
                # % CHANGE
                # --------------------------------------------

                change = float(
                    row["% Change"]
                )

                sign = (
                    "+"
                    if change >= 0
                    else ""
                )

                row_cols[3].markdown(
                    f"""
                    <div class="scanner-row">
                        {sign}{change:.1f}%
                    </div>
                    """,
                    unsafe_allow_html=True
                )


                # --------------------------------------------
                # RELATIVE VOLUME
                # --------------------------------------------

                row_cols[4].markdown(
                    f"""
                    <div class="scanner-row">
                        {row["Rel Vol"]:.1f}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


    # ========================================================
    # RIGHT TRADINGVIEW
    # ========================================================

    with right_col:

        selected = (
            st.session_state.selected_ticker
        )

        st.markdown(
            f"### TradingView — {selected}"
        )

        tradingview_chart(
            selected,
            height=620
        )


# ============================================================
# START
# ============================================================

automatic_scanner()
