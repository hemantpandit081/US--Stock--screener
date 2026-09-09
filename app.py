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

    .block-container {
        padding-top: 0.5rem;
        padding-bottom: 0.2rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }

    .main-title {
        font-size: 24px;
        font-weight: 800;
        margin-bottom: 2px;
    }

    .sub-title {
        font-size: 12px;
        opacity: 0.70;
        margin-bottom: 6px;
    }

    .scanner-header {
        font-size: 12px;
        font-weight: 800;
        padding: 5px 3px;
        border-bottom: 1px solid rgba(128,128,128,0.35);
    }

    .scanner-row {
        padding-top: 2px;
        padding-bottom: 2px;
        border-bottom: 1px solid rgba(128,128,128,0.12);
        font-size: 12px;
    }

    .repeat-square {
        font-size: 22px;
        font-weight: 900;
        line-height: 1;
        margin-left: 2px;
        margin-top: 2px;
        color: white;
    }

    div.stButton > button {
        padding-top: 1px;
        padding-bottom: 1px;
        padding-left: 3px;
        padding-right: 3px;
        min-height: 28px;
        font-size: 12px;
    }

    section[data-testid="stSidebar"] {
        min-width: 270px;
        max-width: 300px;
    }

    div[data-testid="stVerticalBlock"] {
        gap: 0.20rem;
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

NY_TZ = ZoneInfo("America/New_York")


def load_settings():

    if os.path.exists(SETTINGS_FILE):

        try:
            with open(
                SETTINGS_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                saved = json.load(f)

            settings = DEFAULT_SETTINGS.copy()
            settings.update(saved)

            return settings

        except Exception:
            pass

    return DEFAULT_SETTINGS.copy()


def save_settings(settings):

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


if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "AAPL"

if "scanner_data" not in st.session_state:
    st.session_state.scanner_data = pd.DataFrame()

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None


# ============================================================
# MARKET HOURS
# ============================================================

def market_is_open():

    now = datetime.now(NY_TZ)

    if now.weekday() >= 5:
        return False

    market_open = time(9, 30)
    market_close = time(16, 0)

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
                "User-Agent": "Mozilla/5.0"
            },
        )

        response.raise_for_status()

        lines = response.text.splitlines()

        header_index = None

        for i, line in enumerate(lines):

            if line.startswith("Ticker,Name"):

                header_index = i
                break

        if header_index is None:
            raise ValueError(
                "Could not find holdings CSV header."
            )

        csv_text = "\n".join(
            lines[header_index:]
        )

        df = pd.read_csv(
            io.StringIO(csv_text)
        )

        if "Asset Class" in df.columns:

            df = df[
                df["Asset Class"]
                .astype(str)
                .str.lower()
                .eq("equity")
            ]

        if "Location" in df.columns:

            df = df[
                df["Location"]
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
            ~df["Ticker"].isin(invalid)
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

        return [
            "AAPL",
            "AMD",
            "NVDA",
            "TSLA",
            "PLTR",
            "SOFI",
            "IONQ",
            "RKLB",
            "FUBO",
            "MARA",
            "RIOT",
            "HIMS",
            "SOUN",
            "BBAI",
            "OPEN",
        ]


# ============================================================
# YFINANCE DATA
# ============================================================

def get_symbol_data(
    data,
    symbol
):

    if data is None or data.empty:
        return None

    try:

        if isinstance(
            data.columns,
            pd.MultiIndex
        ):

            if (
                symbol
                in data.columns.get_level_values(0)
            ):

                result = data[symbol].copy()

            elif (
                symbol
                in data.columns.get_level_values(1)
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

        result = result.dropna(
            how="all"
        )

        return result

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

    if "Volume" not in session_data.columns:

        return False, 0, 0

    volumes = pd.to_numeric(
        session_data["Volume"],
        errors="coerce"
    ).dropna()

    if len(volumes) < 2:

        return False, 0, 0

    current_volume = float(
        volumes.iloc[-1]
    )

    previous_volumes = volumes.iloc[:-1]

    if previous_volumes.empty:

        return False, current_volume, 0

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
        >= previous_highest * tolerance
    )

    return (
        repeat,
        current_volume,
        previous_highest
    )


# ============================================================
# SCAN BATCH
# ============================================================

def scan_batch(symbols):

    if not symbols:
        return pd.DataFrame()

    results = []

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

    for symbol in symbols:

        try:

            minute_data = get_symbol_data(
                intraday,
                symbol
            )

            daily_data = get_symbol_data(
                daily,
                symbol
            )

            if (
                minute_data is None
                or minute_data.empty
            ):

                continue

            if not all(
                col in minute_data.columns
                for col in [
                    "Close",
                    "Volume"
                ]
            ):

                continue

            minute_data = minute_data.dropna(
                subset=["Close"]
            )

            if minute_data.empty:
                continue

            ltp = float(
                minute_data["Close"].iloc[-1]
            )

            if ltp <= 0:
                continue

            latest_date = (
                minute_data.index[-1].date()
            )

            session_data = (
                minute_data[
                    minute_data.index.date
                    == latest_date
                ].copy()
            )

            if session_data.empty:
                continue

            session_volume = float(
                pd.to_numeric(
                    session_data["Volume"],
                    errors="coerce"
                )
                .fillna(0)
                .sum()
            )

            current_1m_volume = float(
                pd.to_numeric(
                    session_data["Volume"],
                    errors="coerce"
                )
                .fillna(0)
                .iloc[-1]
            )

            repeat, current_volume, previous_spike = (
                detect_repeat(
                    session_data,
                    st.session_state.settings[
                        "repeat_tolerance"
                    ],
                )
            )

            previous_close = np.nan

            if (
                daily_data is not None
                and not daily_data.empty
                and "Close"
                in daily_data.columns
            ):

                daily_close = pd.to_numeric(
                    daily_data["Close"],
                    errors="coerce"
                ).dropna()

                if len(daily_close) >= 2:

                    previous_close = float(
                        daily_close.iloc[-2]
                    )

            if (
                pd.isna(previous_close)
                or previous_close <= 0
            ):

                continue

            percent_change = (
                (
                    ltp
                    - previous_close
                )
                / previous_close
                * 100
            )

            avg_volume = np.nan

            if (
                daily_data is not None
                and not daily_data.empty
                and "Volume"
                in daily_data.columns
            ):

                daily_volume = pd.to_numeric(
                    daily_data["Volume"],
                    errors="coerce"
                ).dropna()

                if len(daily_volume) >= 2:

                    previous_daily_volume = (
                        daily_volume.iloc[:-1]
                    )

                    avg_volume = float(
                        previous_daily_volume
                        .tail(5)
                        .mean()
                    )

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
                        session_data.index[-1],

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

                    "Current 1m Volume":
                        current_1m_volume,

                    "Previous Spike":
                        previous_spike,

                    "Repeat":
                        bool(repeat),
                }
            )

        except Exception:

            continue

    if not results:

        return pd.DataFrame()

    return pd.DataFrame(results)


# ============================================================
# MAIN SCANNER
# ============================================================

def run_scanner():

    settings = (
        st.session_state.settings
    )

    symbols = load_russell_2000()

    max_stocks = int(
        settings["max_stocks"]
    )

    symbols = symbols[
        :max_stocks
    ]

    all_results = []

    batch_size = 50

    if not symbols:

        return pd.DataFrame()

    progress = st.progress(0)

    total = len(symbols)

    for i in range(
        0,
        total,
        batch_size
    ):

        batch = symbols[
            i:i + batch_size
        ]

        batch_result = scan_batch(
            batch
        )

        if (
            batch_result is not None
            and not batch_result.empty
        ):

            all_results.append(
                batch_result
            )

        progress.progress(
            min(
                (i + len(batch)) / total,
                1.0
            )
        )

    progress.empty()

    if not all_results:

        return pd.DataFrame()

    result = pd.concat(
        all_results,
        ignore_index=True
    )

    result = result[
        (result["LTP"]
         >= settings["min_price"])
        &
        (result["LTP"]
         <= settings["max_price"])
        &
        (result["Volume"]
         >= settings["min_volume"])
        &
        (result["Rel Vol"]
         >= settings["min_rvol"])
        &
        (result["% Change"]
         >= settings["min_change"])
    ].copy()

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
        ],
    )

    return result.reset_index(
        drop=True
    )


# ============================================================
# TRADINGVIEW
# ============================================================

def tradingview_chart(
    symbol,
    height=560
):

    import streamlit.components.v1 as components

    tv_symbol = f"NASDAQ:{symbol}"

    html = f"""
    <div
        style="
            width:100%;
            height:{height}px;
            overflow:hidden;
        "
    >

        <div
            class="tradingview-widget-container"
            style="
                height:100%;
                width:100%;
            "
        >

            <div
                class="tradingview-widget-container__widget"
                style="
                    height:100%;
                    width:100%;
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
    '<div class="main-title">'
    '📈 US Momentum Stock Scanner'
    '</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="sub-title">'
    '1-minute momentum scanner • Russell 2000 • TradingView'
    '</div>',
    unsafe_allow_html=True,
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
        ],
    )

    refresh_options = [
        30,
        60,
        90,
        120,
        180,
        300
    ]

    current_refresh = (
        st.session_state.settings[
            "refresh_seconds"
        ]
    )

    if current_refresh not in refresh_options:
        current_refresh = 60

    refresh_seconds = st.selectbox(
        "Refresh interval",
        refresh_options,
        index=refresh_options.index(
            current_refresh
        ),
    )

    st.divider()

    st.subheader(
        "Price"
    )

    min_price = st.number_input(
        "Minimum price",
        min_value=0.01,
        value=float(
            st.session_state.settings[
                "min_price"
            ]
        ),
        step=0.50,
    )

    max_price = st.number_input(
        "Maximum price",
        min_value=0.01,
        value=float(
            st.session_state.settings[
                "max_price"
            ]
        ),
        step=0.50,
    )

    st.subheader(
        "Volume"
    )

    min_volume = st.number_input(
        "Minimum volume",
        min_value=0,
        value=int(
            st.session_state.settings[
                "min_volume"
            ]
        ),
        step=100000,
    )

    min_rvol = st.number_input(
        "Minimum Rel Vol",
        min_value=0.0,
        value=float(
            st.session_state.settings[
                "min_rvol"
            ]
        ),
        step=0.5,
    )

    min_change = st.number_input(
        "Minimum % Change",
        min_value=-100.0,
        value=float(
            st.session_state.settings[
                "min_change"
            ]
        ),
        step=0.5,
    )

    st.subheader(
        "Scanner"
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
        step=50,
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
        step=5,
    )

    st.divider()

    # ========================================================
    # SAVE SETTINGS
    # ========================================================

    if st.button(
        "💾 Save Settings",
        use_container_width=True,
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
                    repeat_percent / 100
                ),

            "refresh_seconds":
                int(refresh_seconds),

            "auto_scan":
                bool(auto_scan),
        }

        if save_settings(
            st.session_state.settings
        ):

            st.success(
                "Settings saved."
            )


    # ========================================================
    # SCAN NOW
    # ========================================================

    if st.button(
        "🔎 Scan Now",
        use_container_width=True,
    ):

        st.session_state.settings[
            "min_price"
        ] = float(min_price)

        st.session_state.settings[
            "max_price"
        ] = float(max_price)

        st.session_state.settings[
            "min_volume"
        ] = int(min_volume)

        st.session_state.settings[
            "min_rvol"
        ] = float(min_rvol)

        st.session_state.settings[
            "min_change"
        ] = float(min_change)

        st.session_state.settings[
            "max_stocks"
        ] = int(max_stocks)

        st.session_state.settings[
            "repeat_tolerance"
        ] = float(
            repeat_percent / 100
        )

        st.session_state.settings[
            "refresh_seconds"
        ] = int(refresh_seconds)

        st.session_state.settings[
            "auto_scan"
        ] = bool(auto_scan)

        with st.spinner(
            "Scanning stocks..."
        ):

            data = run_scanner()

        st.session_state.scanner_data = data

        st.session_state.last_scan = (
            datetime.now()
        )

        st.rerun()


# ============================================================
# AUTOMATIC SCANNER
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


@st.fragment(
    run_every=run_every
)
def automatic_scanner():

    if (
        st.session_state.settings[
            "auto_scan"
        ]
        and market_is_open()
    ):

        with st.spinner(
            "Updating scanner..."
        ):

            data = run_scanner()

        st.session_state.scanner_data = data

        st.session_state.last_scan = (
            datetime.now()
        )

    data = (
        st.session_state.scanner_data
    )

    # ========================================================
    # IMPORTANT:
    # 30% SCANNER
    # 70% TRADINGVIEW
    # ========================================================

    left_col, right_col = st.columns(
        [30, 70],
        gap="small",
    )

    # ========================================================
    # LEFT - SCANNER
    # ========================================================

    with left_col:

        st.markdown(
            "### Scanner"
        )

        if st.session_state.last_scan:

            st.caption(
                "Last update: "
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
                "No stocks currently "
                "match your filters."
            )

        else:

            # Scanner header
            header_cols = st.columns(
                [
                    1.0,
                    1.9,
                    1.0,
                    1.25,
                    1.0
                ]
            )

            header_cols[0].markdown(
                '<div class="scanner-header">'
                'Time'
                '</div>',
                unsafe_allow_html=True,
            )

            header_cols[1].markdown(
                '<div class="scanner-header">'
                'Symbol'
                '</div>',
                unsafe_allow_html=True,
            )

            header_cols[2].markdown(
                '<div class="scanner-header">'
                'LTP'
                '</div>',
                unsafe_allow_html=True,
            )

            header_cols[3].markdown(
                '<div class="scanner-header">'
                '% Change'
                '</div>',
                unsafe_allow_html=True,
            )

            header_cols[4].markdown(
                '<div class="scanner-header">'
                'Rel Vol'
                '</div>',
                unsafe_allow_html=True,
            )

            # =================================================
            # ROWS
            # =================================================

            for _, row in data.iterrows():

                row_cols = st.columns(
                    [
                        1.0,
                        1.9,
                        1.0,
                        1.25,
                        1.0
                    ]
                )

                # Time
                try:

                    row_time = pd.to_datetime(
                        row["Time"]
                    ).strftime(
                        "%H:%M"
                    )

                except Exception:

                    row_time = "--"

                row_cols[0].markdown(
                    f'<div class="scanner-row">'
                    f'{row_time}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # =================================================
                # SYMBOL + REPEAT SQUARE
                # =================================================

                symbol_container = (
                    row_cols[1].container()
                )

                symbol_inner = (
                    symbol_container.columns(
                        [1.0, 0.28]
                    )
                )

                ticker = str(
                    row["Symbol"]
                )

                if symbol_inner[0].button(
                    ticker,
                    key=(
                        f'ticker_'
                        f'{ticker}_'
                        f'{row["Time"]}'
                    ),
                    use_container_width=True,
                ):

                    st.session_state.selected_ticker = (
                        ticker
                    )

                    st.rerun()

                # BIG WHITE REPEAT SQUARE
                if bool(
                    row["Repeat"]
                ):

                    symbol_inner[1].markdown(
                        """
                        <div
                            class="repeat-square"
                            title="Repeat volume signal"
                        >
                            ■
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # LTP
                row_cols[2].markdown(
                    f'<div class="scanner-row">'
                    f'${row["LTP"]:.2f}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Change
                change = float(
                    row["% Change"]
                )

                sign = (
                    "+"
                    if change >= 0
                    else ""
                )

                row_cols[3].markdown(
                    f'<div class="scanner-row">'
                    f'{sign}'
                    f'{change:.2f}%'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Relative volume
                row_cols[4].markdown(
                    f'<div class="scanner-row">'
                    f'{row["Rel Vol"]:.1f}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ========================================================
    # RIGHT - TRADINGVIEW
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
            height=560
        )


# ============================================================
# START
# ============================================================

automatic_scanner()
