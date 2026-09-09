import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import io
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="US Stock Momentum Scanner",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

        .block-container {
            padding-top: 0.6rem;
            padding-bottom: 0.2rem;
            padding-left: 0.7rem;
            padding-right: 0.7rem;
        }

        div[data-testid="stHorizontalBlock"] {
            gap: 0.25rem;
        }

        div[data-testid="stButton"] > button {
            padding-top: 0.15rem;
            padding-bottom: 0.15rem;
            min-height: 30px;
        }

        .scanner-header {
            font-weight: 700;
            font-size: 14px;
            padding-bottom: 4px;
            border-bottom: 1px solid rgba(128,128,128,0.35);
            margin-bottom: 2px;
        }

        .repeat-square {
            font-size: 18px;
            font-weight: 900;
            margin-left: 3px;
            line-height: 1;
            vertical-align: middle;
        }

        .last-update {
            font-size: 11px;
            opacity: 0.65;
            margin-bottom: 4px;
        }

        .scanner-title {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 2px;
        }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# DEFAULT SETTINGS
# ============================================================

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


# ============================================================
# SESSION STATE
# ============================================================

if "settings" not in st.session_state:
    st.session_state.settings = DEFAULT_SETTINGS.copy()

if "scanner_data" not in st.session_state:
    st.session_state.scanner_data = pd.DataFrame()

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "AAPL"

if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None

if "manual_scan_requested" not in st.session_state:
    st.session_state.manual_scan_requested = False


# ============================================================
# SETTINGS FILE
# ============================================================

SETTINGS_FILE = "scanner_settings.csv"


def save_settings(settings):

    df = pd.DataFrame([settings])
    df.to_csv(
        SETTINGS_FILE,
        index=False
    )


def load_settings():

    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()

    try:

        df = pd.read_csv(
            SETTINGS_FILE
        )

        if df.empty:
            return DEFAULT_SETTINGS.copy()

        saved = df.iloc[0].to_dict()

        settings = DEFAULT_SETTINGS.copy()

        for key in settings:

            if (
                key in saved
                and pd.notna(saved[key])
            ):
                settings[key] = saved[key]

        settings["min_price"] = float(
            settings["min_price"]
        )

        settings["max_price"] = float(
            settings["max_price"]
        )

        settings["min_volume"] = int(
            settings["min_volume"]
        )

        settings["min_rvol"] = float(
            settings["min_rvol"]
        )

        settings["min_change"] = float(
            settings["min_change"]
        )

        settings["max_stocks"] = int(
            settings["max_stocks"]
        )

        settings["repeat_tolerance"] = float(
            settings["repeat_tolerance"]
        )

        settings["refresh_seconds"] = int(
            settings["refresh_seconds"]
        )

        settings["auto_scan"] = bool(
            settings["auto_scan"]
        )

        return settings

    except Exception:

        return DEFAULT_SETTINGS.copy()


if "settings_loaded" not in st.session_state:

    st.session_state.settings = (
        load_settings()
    )

    st.session_state.settings_loaded = True


# ============================================================
# MARKET HOURS
# ============================================================

def market_is_open():

    eastern = ZoneInfo(
        "America/New_York"
    )

    now = datetime.now(
        eastern
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
# LOAD RUSSELL 2000
# ============================================================

@st.cache_data(ttl=3600)
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

        text = response.content.decode(
            "utf-8",
            errors="ignore"
        )

        lines = text.splitlines()

        header_index = None

        for i, line in enumerate(lines):

            if line.startswith(
                "Ticker,Name"
            ):

                header_index = i
                break

        if header_index is None:
            return []

        csv_text = "\n".join(
            lines[header_index:]
        )

        df = pd.read_csv(
            io.StringIO(csv_text)
        )

        if "Ticker" not in df.columns:
            return []

        if "Asset Class" in df.columns:

            df = df[
                df["Asset Class"]
                .astype(str)
                .str.upper()
                .eq("EQUITY")
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

        symbols = []

        for ticker in (
            df["Ticker"]
            .astype(str)
        ):

            ticker = (
                ticker
                .strip()
                .upper()
            )

            if not ticker:
                continue

            if ticker == "CASH":
                continue

            ticker = ticker.replace(
                ".",
                "-"
            )

            symbols.append(
                ticker
            )

        symbols = list(
            dict.fromkeys(
                symbols
            )
        )

        return symbols

    except Exception as e:

        st.error(
            f"Unable to load Russell 2000 holdings: {e}"
        )

        return []


# ============================================================
# YFINANCE DATA HELPER
# ============================================================

def get_symbol_data(
    data,
    symbol
):

    try:

        if (
            data is None
            or data.empty
        ):
            return None

        if isinstance(
            data.columns,
            pd.MultiIndex
        ):

            if (
                symbol
                in data.columns
                .get_level_values(0)
            ):

                return data[symbol]

            for level in range(
                data.columns.nlevels
            ):

                values = (
                    data.columns
                    .get_level_values(level)
                    .astype(str)
                )

                if symbol in values:

                    try:

                        return data.xs(
                            symbol,
                            level=level,
                            axis=1
                        )

                    except Exception:
                        pass

            return None

        return data

    except Exception:

        return None


# ============================================================
# REPEAT VOLUME DETECTION
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

    if previous_volumes.empty:
        return False, current_volume, 0

    previous_highest = float(
        previous_volumes.max()
    )

    if previous_highest <= 0:
        return False, current_volume, 0

    repeat_level = (
        previous_highest
        * tolerance
    )

    repeat = (
        current_volume
        >= repeat_level
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

    results = []

    if not symbols:
        return pd.DataFrame()

    try:

        intraday = yf.download(
            tickers=symbols,
            period="1d",
            interval="1m",
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            threads=True,
            progress=False
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
            progress=False
        )

    except Exception:

        daily = pd.DataFrame()


    # ========================================================
    # PROCESS STOCKS
    # ========================================================

    for symbol in symbols:

        try:

            intraday_symbol = (
                get_symbol_data(
                    intraday,
                    symbol
                )
            )

            if (
                intraday_symbol is None
                or intraday_symbol.empty
            ):
                continue

            intraday_symbol = (
                intraday_symbol
                .dropna(
                    subset=["Close"],
                    how="all"
                )
            )

            if intraday_symbol.empty:
                continue


            # ------------------------------------------------
            # LTP
            # ------------------------------------------------

            latest_close = pd.to_numeric(
                intraday_symbol["Close"],
                errors="coerce"
            ).dropna()

            if latest_close.empty:
                continue

            ltp = float(
                latest_close.iloc[-1]
            )


            # ------------------------------------------------
            # SESSION VOLUME
            # ------------------------------------------------

            volume_series = pd.to_numeric(
                intraday_symbol["Volume"],
                errors="coerce"
            ).fillna(0)

            session_volume = float(
                volume_series.sum()
            )


            # ------------------------------------------------
            # REPEAT SIGNAL
            # ------------------------------------------------

            repeat, current_1m_volume, previous_spike = (
                detect_repeat(
                    intraday_symbol,
                    st.session_state.settings[
                        "repeat_tolerance"
                    ]
                )
            )


            # ------------------------------------------------
            # PREVIOUS CLOSE
            # ------------------------------------------------

            previous_close = None

            daily_symbol = (
                get_symbol_data(
                    daily,
                    symbol
                )
            )

            if (
                daily_symbol is not None
                and not daily_symbol.empty
            ):

                closes = pd.to_numeric(
                    daily_symbol["Close"],
                    errors="coerce"
                ).dropna()

                if len(closes) >= 2:

                    previous_close = float(
                        closes.iloc[-2]
                    )


            # ------------------------------------------------
            # % CHANGE
            # ------------------------------------------------

            if (
                previous_close is not None
                and previous_close > 0
            ):

                percent_change = (
                    (
                        ltp
                        - previous_close
                    )
                    / previous_close
                    * 100
                )

            else:

                percent_change = 0.0


            # ------------------------------------------------
            # RELATIVE VOLUME
            # ------------------------------------------------

            relative_volume = 0.0

            if (
                daily_symbol is not None
                and not daily_symbol.empty
            ):

                daily_volume = pd.to_numeric(
                    daily_symbol["Volume"],
                    errors="coerce"
                ).dropna()

                if len(daily_volume) >= 6:

                    previous_daily_volume = (
                        daily_volume
                        .iloc[:-1]
                        .tail(5)
                    )

                    avg_previous_volume = (
                        previous_daily_volume.mean()
                    )

                    if (
                        avg_previous_volume
                        and avg_previous_volume > 0
                    ):

                        relative_volume = (
                            session_volume
                            / avg_previous_volume
                        )


            # ------------------------------------------------
            # FILTERS
            # ------------------------------------------------

            settings = (
                st.session_state.settings
            )

            if (
                ltp
                < settings["min_price"]
            ):
                continue

            if (
                ltp
                > settings["max_price"]
            ):
                continue

            if (
                session_volume
                < settings["min_volume"]
            ):
                continue

            if (
                relative_volume
                < settings["min_rvol"]
            ):
                continue

            if (
                percent_change
                < settings["min_change"]
            ):
                continue


            # ------------------------------------------------
            # TIME
            # ------------------------------------------------

            try:

                last_timestamp = (
                    intraday_symbol.index[-1]
                )

                if hasattr(
                    last_timestamp,
                    "strftime"
                ):

                    display_time = (
                        last_timestamp
                        .strftime("%H:%M")
                    )

                else:

                    display_time = ""

            except Exception:

                display_time = ""


            # ------------------------------------------------
            # RESULT
            # ------------------------------------------------

            results.append(
                {
                    "Time":
                        display_time,

                    "Symbol":
                        symbol,

                    "LTP":
                        ltp,

                    "% Change":
                        percent_change,

                    "Rel Vol":
                        relative_volume,

                    "Repeat":
                        repeat,

                    "Current 1m Volume":
                        current_1m_volume,

                    "Previous Spike":
                        previous_spike,

                    "Session Volume":
                        session_volume,
                }
            )

        except Exception:

            continue


    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(
        results
    )

    result_df = result_df.sort_values(
        by=[
            "% Change",
            "Rel Vol"
        ],
        ascending=False
    )

    return result_df.reset_index(
        drop=True
    )


# ============================================================
# RUN SCANNER
# ============================================================

def run_scanner():

    symbols = (
        load_russell_2000()
    )

    if not symbols:
        return pd.DataFrame()

    max_stocks = int(
        st.session_state.settings[
            "max_stocks"
        ]
    )

    symbols = symbols[
        :max_stocks
    ]

    all_results = []

    batch_size = 50

    for start in range(
        0,
        len(symbols),
        batch_size
    ):

        batch = symbols[
            start:start + batch_size
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

    final_df = pd.concat(
        all_results,
        ignore_index=True
    )

    final_df = final_df.sort_values(
        by=[
            "% Change",
            "Rel Vol"
        ],
        ascending=False
    )

    return final_df.reset_index(
        drop=True
    )


# ============================================================
# TRADINGVIEW CHART
# ============================================================

def tradingview_chart(
    symbol
):

    html = f"""
    <div style="
        width:100%;
        height:560px;
        overflow:hidden;
        position:relative;
    ">

        <iframe
            src="https://www.tradingview.com/widgetembed/?frameElementId=tradingview_chart&symbol=NASDAQ%3A{symbol}&interval=1&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=%5B%5D&hideideas=1&theme=dark&style=1&timezone=exchange&withdateranges=1&hidevolume=0&allow_symbol_change=1&details=1&hotlist=1&calendar=1"
            style="
                width:100%;
                height:100%;
                border:0;
            "
            allowtransparency="true"
            frameborder="0"
            allowfullscreen
        >
        </iframe>

    </div>
    """

    st.components.v1.html(
        html,
        height=560
    )


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown(
        "## Scanner Settings"
    )

    auto_scan = st.checkbox(
        "Auto Scanner",
        value=bool(
            st.session_state.settings[
                "auto_scan"
            ]
        )
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

    if current_refresh not in refresh_options:
        current_refresh = 60

    refresh_seconds = st.selectbox(
        "Refresh interval",
        refresh_options,
        index=refresh_options.index(
            current_refresh
        )
    )

    max_stocks = st.number_input(
        "Maximum Russell 2000 stocks",
        min_value=50,
        max_value=2000,
        value=int(
            st.session_state.settings[
                "max_stocks"
            ]
        ),
        step=50
    )

    st.markdown("---")

    st.markdown(
        "### Price"
    )

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
        step=1.00
    )

    st.markdown(
        "### Volume"
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
        min_value=0.0,
        value=float(
            st.session_state.settings[
                "min_change"
            ]
        ),
        step=0.5
    )

    st.markdown(
        "### Repeat Signal"
    )

    repeat_percent = st.slider(
        "Current 1-minute volume vs previous high",
        min_value=50,
        max_value=100,
        value=int(
            float(
                st.session_state.settings[
                    "repeat_tolerance"
                ]
            )
            * 100
        ),
        step=5
    )

    st.markdown("---")

    if st.button(
        "Save Settings",
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
                float(repeat_percent)
                / 100,

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

    if st.button(
        "Scan Now",
        use_container_width=True
    ):

        st.session_state.settings[
            "auto_scan"
        ]["auto_scan"] = bool(auto_scan)

        st.session_state.settings[
            "refresh_seconds"
        ] = int(
            refresh_seconds
        )

        st.session_state.manual_scan_requested = True

        st.rerun()


# ============================================================
# CURRENT SETTINGS
# ============================================================

st.session_state.settings[
    "auto_scan"
] = auto_scan

st.session_state.settings[
    "refresh_seconds"
] = int(
    refresh_seconds
)


# ============================================================
# TITLE
# ============================================================

st.markdown(
    """
    <div class="scanner-title">
        US Stock Momentum Scanner
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# MARKET STATUS
# ============================================================

if market_is_open():

    st.markdown(
        "🟢 **US Market Open**"
    )

else:

    st.markdown(
        "⚪ **US Market Closed**"
    )


# ============================================================
# MAIN LAYOUT
# ============================================================

scanner_col, chart_col = st.columns(
    [35, 65]
)


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
        f'{int(st.session_state.settings["refresh_seconds"])}s'
    )


@st.fragment(
    run_every=run_every
)
def automatic_scanner():

    # ========================================================
    # RUN SCAN
    # ========================================================

    should_scan = False

    if market_is_open():

        if (
            st.session_state.scanner_data.empty
        ):

            should_scan = True

        elif (
            st.session_state.manual_scan_requested
        ):

            should_scan = True

        elif (
            st.session_state.settings[
                "auto_scan"
            ]
        ):

            should_scan = True


    if should_scan:

        with st.spinner(
            "Scanning..."
        ):

            data = run_scanner()

        st.session_state.scanner_data = data

        st.session_state.last_scan_time = (
            datetime.now()
        )

        st.session_state.manual_scan_requested = False


    # ========================================================
    # LEFT — SCANNER
    # ========================================================

    with scanner_col:

        if (
            st.session_state.last_scan_time
            is not None
        ):

            update_text = (
                "Updated: "
                +
                st.session_state.last_scan_time.strftime(
                    "%H:%M:%S"
                )
            )

            st.markdown(
                f"""
                <div class="last-update">
                    {update_text}
                </div>
                """,
                unsafe_allow_html=True
            )


        # ----------------------------------------------------
        # HEADERS
        # ----------------------------------------------------

        headers = [
            "Time",
            "Symbol",
            "LTP",
            "% Change",
            "Rel Vol"
        ]

        header_cols = st.columns(
            [
                0.8,
                1.45,
                1.0,
                1.0,
                1.0
            ]
        )

        for i, header in enumerate(
            headers
        ):

            header_cols[i].markdown(
                f"""
                <div class="scanner-header">
                    {header}
                </div>
                """,
                unsafe_allow_html=True
            )


        # ----------------------------------------------------
        # SCANNER DATA
        # ----------------------------------------------------

        data = (
            st.session_state.scanner_data
        )

        if data.empty:

            st.info(
                "No stocks currently match the filters."
            )

        else:

            for _, row in data.iterrows():

                row_cols = st.columns(
                    [
                        0.8,
                        1.45,
                        1.0,
                        1.0,
                        1.0
                    ]
                )


                # --------------------------------------------
                # TIME
                # --------------------------------------------

                row_cols[0].write(
                    row["Time"]
                )


                # --------------------------------------------
                # SYMBOL + SOLID SQUARE
                # --------------------------------------------

                symbol_container = (
                    row_cols[1].container()
                )

                symbol_inner = (
                    symbol_container.columns(
                        [
                            1.0,
                            0.25
                        ]
                    )
                )


                # --------------------------------------------
                # TICKER
                # --------------------------------------------

                if symbol_inner[0].button(
                    row["Symbol"],
                    key=(
                        f"ticker_"
                        f"{row['Symbol']}_"
                        f"{row['Time']}"
                    ),
                    use_container_width=True
                ):

                    st.session_state.selected_ticker = (
                        row["Symbol"]
                    )

                    st.rerun()


                # --------------------------------------------
                # REPEAT SQUARE
                # --------------------------------------------

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
                        unsafe_allow_html=True
                    )


                # --------------------------------------------
                # LTP
                # --------------------------------------------

                row_cols[2].write(
                    f"${row['LTP']:.2f}"
                )


                # --------------------------------------------
                # % CHANGE
                # --------------------------------------------

                row_cols[3].write(
                    f"{row['% Change']:.2f}%"
                )


                # --------------------------------------------
                # REL VOL
                # --------------------------------------------

                row_cols[4].write(
                    f"{row['Rel Vol']:.1f}"
                )


    # ========================================================
    # RIGHT — TRADINGVIEW
    # ========================================================

    with chart_col:

        selected = (
            st.session_state.selected_ticker
        )

        st.markdown(
            f"### {selected}"
        )

        tradingview_chart(
            selected
        )


# ============================================================
# START
# ============================================================

automatic_scanner()
