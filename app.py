import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from io import StringIO
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components
import json
import os
import time


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Russell 2000 Momentum Scanner",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

html, body {
    margin: 0;
    padding: 0;
}

.block-container {
    padding-top: 0.25rem !important;
    padding-bottom: 0rem !important;
    padding-left: 0.7rem !important;
    padding-right: 0.7rem !important;
    max-width: 100% !important;
}

h1 {
    margin-top: 0 !important;
    margin-bottom: 0.05rem !important;
    font-size: 1.7rem !important;
}

h2, h3 {
    margin-top: 0 !important;
    margin-bottom: 0.15rem !important;
}

div[data-testid="stHorizontalBlock"] {
    gap: 0.4rem !important;
}

div[data-testid="stVerticalBlock"] {
    gap: 0.25rem;
}

.repeat-signal {
    font-size: 18px;
    font-weight: bold;
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
    "min_change": 2.0,
    "max_stocks": 300,
    "repeat_tolerance": 0.90
}


# ============================================================
# RUSSELL 2000 HOLDINGS
# ============================================================

RUSSELL_2000_URL = (
    "https://www.ishares.com/us/products/239710/"
    "ishares-russell-2000-etf/latest-holdings.csv"
)


# ============================================================
# LOAD SETTINGS
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
# INITIAL SETTINGS
# ============================================================

if "settings_loaded" not in st.session_state:

    saved_settings = load_saved_settings()

    st.session_state.min_price = saved_settings["min_price"]
    st.session_state.max_price = saved_settings["max_price"]
    st.session_state.min_volume = saved_settings["min_volume"]
    st.session_state.min_rvol = saved_settings["min_rvol"]
    st.session_state.min_change = saved_settings["min_change"]
    st.session_state.max_stocks = saved_settings["max_stocks"]
    st.session_state.repeat_tolerance = saved_settings[
        "repeat_tolerance"
    ]

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

if "russell_symbols" not in st.session_state:
    st.session_state.russell_symbols = []

if "russell_exchanges" not in st.session_state:
    st.session_state.russell_exchanges = {}

if "russell_loaded" not in st.session_state:
    st.session_state.russell_loaded = False


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
# LOAD RUSSELL 2000
# ============================================================

@st.cache_data(ttl=3600)
def load_russell_2000():

    try:

        response = requests.get(
            RUSSELL_2000_URL,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=30
        )

        response.raise_for_status()

        # ----------------------------------------------------
        # Find CSV header
        # ----------------------------------------------------

        lines = response.text.splitlines()

        header_index = None

        for i, line in enumerate(lines):

            if line.startswith("Ticker,Name"):

                header_index = i
                break

        if header_index is None:

            raise ValueError(
                "Could not find Russell 2000 holdings header."
            )

        csv_text = "\n".join(
            lines[header_index:]
        )

        df = pd.read_csv(
            StringIO(csv_text)
        )

        # ----------------------------------------------------
        # Keep equities only
        # ----------------------------------------------------

        df = df[
            df["Asset Class"]
            .astype(str)
            .str.lower()
            .eq("equity")
        ].copy()

        # ----------------------------------------------------
        # Keep US securities
        # ----------------------------------------------------

        df = df[
            df["Location"]
            .astype(str)
            .str.contains(
                "United States",
                case=False,
                na=False
            )
        ].copy()

        # ----------------------------------------------------
        # Clean ticker
        # ----------------------------------------------------

        df["Ticker"] = (
            df["Ticker"]
            .astype(str)
            .str.strip()
        )

        df["Ticker"] = (
            df["Ticker"]
            .str.replace(
                ".",
                "-",
                regex=False
            )
        )

        # ----------------------------------------------------
        # Remove invalid tickers
        # ----------------------------------------------------

        df = df[
            df["Ticker"].notna()
            & (df["Ticker"] != "")
            & (df["Ticker"] != "nan")
        ]

        df = df.drop_duplicates(
            subset=["Ticker"]
        )

        # ----------------------------------------------------
        # Exchange mapping
        # ----------------------------------------------------

        exchange_map = {}

        for _, row in df.iterrows():

            ticker = row["Ticker"]

            exchange = str(
                row.get(
                    "Exchange",
                    ""
                )
            ).upper()

            if "NASDAQ" in exchange:

                exchange_map[ticker] = "NASDAQ"

            elif "NYSE MKT" in exchange:

                exchange_map[ticker] = "AMEX"

            elif "NYSE" in exchange:

                exchange_map[ticker] = "NYSE"

            elif "ARCA" in exchange:

                exchange_map[ticker] = "AMEX"

            else:

                exchange_map[ticker] = "NASDAQ"

        symbols = df["Ticker"].tolist()

        return symbols, exchange_map

    except Exception as e:

        raise RuntimeError(
            f"Could not load Russell 2000: {e}"
        )


# ============================================================
# LOAD RUSSELL INTO SESSION
# ============================================================

if not st.session_state.russell_loaded:

    try:

        (
            russell_symbols,
            russell_exchanges
        ) = load_russell_2000()

        st.session_state.russell_symbols = (
            russell_symbols
        )

        st.session_state.russell_exchanges = (
            russell_exchanges
        )

        st.session_state.russell_loaded = True

    except Exception as e:

        st.error(str(e))


# ============================================================
# REPEAT VOLUME DETECTION
# ============================================================

def detect_repeat_volume(
    session_data,
    tolerance=0.90
):

    """
    Detect repeated intraday volume spikes.

    Logic:

    1. Work with 5-minute candles.
    2. Look at volume from oldest to newest.
    3. Keep track of the previous significant volume spike.
    4. A later candle is marked as Repeat when:
           current volume >= previous spike * tolerance
       OR
           current volume >= previous spike
    5. After a repeat occurs, the larger volume becomes
       the new reference spike.

    Example:

        First spike     100,000
        Later volume     92,000  -> 🔁
        Later volume    150,000  -> 🔁
        Later volume    140,000  -> 🔁
    """

    if session_data.empty:
        return False, 0

    if "Volume" not in session_data.columns:
        return False, 0

    volumes = (
        pd.to_numeric(
            session_data["Volume"],
            errors="coerce"
        )
        .fillna(0)
        .tolist()
    )

    if not volumes:
        return False, 0

    # Remove zero-volume candles
    volumes = [
        float(v)
        for v in volumes
        if float(v) > 0
    ]

    if len(volumes) < 2:
        return False, 0

    # --------------------------------------------------------
    # We need a meaningful first spike.
    # Use the first candle as initial reference.
    # --------------------------------------------------------

    previous_spike = volumes[0]

    repeat_found = False
    repeat_count = 0

    for current_volume in volumes[1:]:

        if previous_spike <= 0:
            previous_spike = current_volume
            continue

        repeat_threshold = (
            previous_spike * tolerance
        )

        # ----------------------------------------------------
        # Current candle has approximately the same
        # or higher volume than the previous spike.
        # ----------------------------------------------------

        if current_volume >= repeat_threshold:

            repeat_found = True
            repeat_count += 1

            # If current volume is larger, make it
            # the new reference spike.
            if current_volume > previous_spike:

                previous_spike = current_volume

        else:

            # If volume is much lower, keep watching.
            # A significantly larger new candle becomes
            # the next volume spike reference.
            if current_volume > previous_spike:

                previous_spike = current_volume

    return repeat_found, repeat_count


# ============================================================
# GET CURRENT REPEAT SIGNAL
# ============================================================

def get_current_repeat_signal(
    session_data,
    tolerance=0.90
):

    """
    Checks whether the CURRENT 5-minute candle is a repeat
    of a previous volume spike.

    The previous spike is determined from candles before
    the current candle.
    """

    if session_data.empty:
        return False, 0

    if "Volume" not in session_data.columns:
        return False, 0

    if len(session_data) < 2:
        return False, 0

    volumes = (
        pd.to_numeric(
            session_data["Volume"],
            errors="coerce"
        )
        .fillna(0)
        .tolist()
    )

    if len(volumes) < 2:
        return False, 0

    current_volume = float(
        volumes[-1]
    )

    previous_volumes = [
        float(v)
        for v in volumes[:-1]
        if float(v) > 0
    ]

    if not previous_volumes:
        return False, 0

    # --------------------------------------------------------
    # Find previous significant volume spike.
    #
    # We use the maximum previous volume as the main
    # reference because the user's requirement is:
    #
    # "coming again with almost same or more as previous volume"
    # --------------------------------------------------------

    previous_spike = max(
        previous_volumes
    )

    if previous_spike <= 0:
        return False, 0

    threshold = (
        previous_spike * tolerance
    )

    if current_volume >= threshold:

        return True, previous_spike

    return False, previous_spike


# ============================================================
# BATCH SCAN
# ============================================================

def scan_batch(symbols):

    results = []

    if not symbols:
        return results

    # ========================================================
    # INTRADAY DATA
    # ========================================================

    try:

        intraday = yf.download(
            tickers=symbols,
            period="5d",
            interval="5m",
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            threads=True,
            progress=False
        )

    except Exception as e:

        print(
            f"Intraday download error: {e}"
        )

        return results

    # ========================================================
    # DAILY DATA
    # ========================================================

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

    except Exception as e:

        print(
            f"Daily download error: {e}"
        )

        return results

    # ========================================================
    # PROCESS EACH STOCK
    # ========================================================

    for symbol in symbols:

        try:

            # ------------------------------------------------
            # GET INTRADAY SYMBOL DATA
            # ------------------------------------------------

            if len(symbols) == 1:

                symbol_intraday = (
                    intraday.copy()
                )

            else:

                if (
                    not isinstance(
                        intraday.columns,
                        pd.MultiIndex
                    )
                ):

                    continue

                if (
                    symbol
                    not in
                    intraday.columns.get_level_values(0)
                ):

                    continue

                symbol_intraday = (
                    intraday[symbol]
                    .copy()
                )

            if symbol_intraday.empty:
                continue

            # ------------------------------------------------
            # Required columns
            # ------------------------------------------------

            if (
                "Close"
                not in symbol_intraday.columns
                or
                "Volume"
                not in symbol_intraday.columns
            ):

                continue

            symbol_intraday = (
                symbol_intraday
                .dropna(
                    subset=[
                        "Close",
                        "Volume"
                    ]
                )
            )

            if symbol_intraday.empty:
                continue

            # ------------------------------------------------
            # Latest trading session
            # ------------------------------------------------

            latest_date = (
                symbol_intraday.index[-1]
                .date()
            )

            session_data = (
                symbol_intraday[
                    symbol_intraday.index.date
                    == latest_date
                ].copy()
            )

            if session_data.empty:
                continue

            # ------------------------------------------------
            # LTP
            # ------------------------------------------------

            ltp = float(
                session_data[
                    "Close"
                ].iloc[-1]
            )

            # ------------------------------------------------
            # Current session volume
            # ------------------------------------------------

            session_volume = float(
                session_data[
                    "Volume"
                ].sum()
            )

            # =================================================
            # CURRENT 5-MINUTE VOLUME
            # =================================================

            current_5m_volume = float(
                session_data[
                    "Volume"
                ].iloc[-1]
            )

            # =================================================
            # REPEAT SIGNAL
            # =================================================

            repeat_signal, previous_spike = (
                get_current_repeat_signal(
                    session_data,
                    st.session_state.repeat_tolerance
                )
            )

            # =================================================
            # DAILY DATA
            # =================================================

            if len(symbols) == 1:

                symbol_daily = (
                    daily.copy()
                )

            else:

                if (
                    not isinstance(
                        daily.columns,
                        pd.MultiIndex
                    )
                ):

                    continue

                if (
                    symbol
                    not in
                    daily.columns.get_level_values(0)
                ):

                    continue

                symbol_daily = (
                    daily[symbol]
                    .copy()
                )

            if symbol_daily.empty:
                continue

            if (
                "Close"
                not in symbol_daily.columns
                or
                "Volume"
                not in symbol_daily.columns
            ):

                continue

            symbol_daily = (
                symbol_daily
                .dropna(
                    subset=[
                        "Close",
                        "Volume"
                    ]
                )
            )

            if len(symbol_daily) < 6:
                continue

            # =================================================
            # PREVIOUS CLOSE
            # =================================================

            previous_close = float(
                symbol_daily[
                    "Close"
                ].iloc[-2]
            )

            if previous_close <= 0:
                continue

            # =================================================
            # PERCENT CHANGE
            # =================================================

            percent_change = (
                (
                    ltp
                    - previous_close
                )
                / previous_close
                * 100
            )

            # =================================================
            # PREVIOUS 5 DAYS VOLUME
            # =================================================

            previous_volumes = (
                symbol_daily[
                    "Volume"
                ].iloc[-6:-1]
            )

            average_daily_volume = float(
                previous_volumes.mean()
            )

            # =================================================
            # RELATIVE VOLUME
            # =================================================

            if average_daily_volume > 0:

                relative_volume = (
                    session_volume
                    / average_daily_volume
                )

            else:

                relative_volume = 0

            # =================================================
            # TIME
            # =================================================

            latest_timestamp = (
                session_data.index[-1]
            )

            try:

                latest_timestamp = (
                    latest_timestamp
                    .tz_convert(
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

            # =================================================
            # RESULT
            # =================================================

            results.append({

                "Time":
                    time_string,

                "Symbol":
                    symbol,

                "LTP":
                    ltp,

                "% Change":
                    percent_change,

                "Rel Vol":
                    relative_volume,

                "Volume":
                    session_volume,

                "5M Volume":
                    current_5m_volume,

                "Repeat":
                    repeat_signal,

                "Previous Spike":
                    previous_spike

            })

        except Exception as e:

            print(
                f"Error processing {symbol}: {e}"
            )

    return results


# ============================================================
# RUN SCANNER
# ============================================================

def run_scanner():

    symbols = (
        st.session_state.russell_symbols
    )

    if not symbols:

        return []

    # --------------------------------------------------------
    # Maximum stocks
    # --------------------------------------------------------

    max_stocks = int(
        st.session_state.max_stocks
    )

    symbols = symbols[
        :max_stocks
    ]

    # --------------------------------------------------------
    # Batch size
    # --------------------------------------------------------

    batch_size = 100

    batches = [
        symbols[i:i + batch_size]
        for i in range(
            0,
            len(symbols),
            batch_size
        )
    ]

    all_results = []

    progress = st.progress(0)

    status = st.empty()

    total_symbols = len(symbols)

    completed = 0

    # ========================================================
    # PROCESS BATCHES
    # ========================================================

    for batch_number, batch in enumerate(
        batches,
        start=1
    ):

        status.text(
            f"Scanning Russell 2000 "
            f"batch {batch_number}/{len(batches)} "
            f"• {completed}/{total_symbols} stocks"
        )

        batch_results = scan_batch(
            batch
        )

        all_results.extend(
            batch_results
        )

        completed += len(batch)

        progress.progress(
            min(
                completed / total_symbols,
                1.0
            )
        )

        time.sleep(0.5)

    progress.empty()
    status.empty()

    return all_results


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

    st.write(
        "Universe: **Russell 2000**"
    )

    st.caption(
        f"{len(st.session_state.russell_symbols):,} "
        "Russell 2000 holdings loaded"
    )

    # --------------------------------------------------------
    # MAX STOCKS
    # --------------------------------------------------------

    st.session_state.max_stocks = (
        st.number_input(
            "Maximum Stocks to Scan",
            min_value=50,
            max_value=max(
                len(
                    st.session_state.russell_symbols
                ),
                50
            ),
            value=min(
                int(
                    st.session_state.max_stocks
                ),
                max(
                    len(
                        st.session_state.russell_symbols
                    ),
                    50
                )
            ),
            step=50
        )
    )

    st.caption(
        "300 is recommended for testing. "
        "Increase toward the full Russell 2000 later."
    )

    # --------------------------------------------------------
    # PRICE
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
    # VOLUME
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
    # RVOL
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
    # % CHANGE
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

    # --------------------------------------------------------
    # REPEAT TOLERANCE
    # --------------------------------------------------------

    repeat_percent = st.slider(
        "Repeat Volume Threshold",
        min_value=50,
        max_value=100,
        value=int(
            st.session_state.repeat_tolerance
            * 100
        ),
        step=5,
        help=(
            "Example: 90% means a new 5-minute volume "
            "candle must be at least 90% of the previous "
            "volume spike to receive 🔁."
        )
    )

    st.session_state.repeat_tolerance = (
        repeat_percent / 100
    )

    st.caption(
        f"🔁 Repeat = current 5-minute volume is "
        f"{repeat_percent}% or more of the previous "
        f"largest 5-minute volume spike."
    )

    st.markdown("---")

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

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
                st.session_state.min_change,

            "max_stocks":
                st.session_state.max_stocks,

            "repeat_tolerance":
                st.session_state.repeat_tolerance

        }

        if save_settings(
            settings_to_save
        ):

            st.success(
                "Filter settings saved!"
            )

    # --------------------------------------------------------
    # RESET
    # --------------------------------------------------------

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

        st.session_state.max_stocks = (
            DEFAULT_SETTINGS["max_stocks"]
        )

        st.session_state.repeat_tolerance = (
            DEFAULT_SETTINGS["repeat_tolerance"]
        )

        st.rerun()

    st.markdown("---")

    # --------------------------------------------------------
    # SCAN BUTTON
    # --------------------------------------------------------

    scan_button = st.button(
        "🔍 Scan Russell 2000",
        use_container_width=True,
        type="primary"
    )


# ============================================================
# RUN SCANNER
# ============================================================

if scan_button:

    with st.spinner(
        "Scanning Russell 2000 stocks..."
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
# LAST SCAN
# ============================================================

if st.session_state.last_scan_time:

    st.caption(
        "Last scan: "
        + st.session_state.last_scan_time
    )


# ============================================================
# MAIN LAYOUT
# ============================================================

scanner_col, chart_col = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT — SCANNER
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

        # ====================================================
        # APPLY FILTERS
        # ====================================================

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

        # ====================================================
        # SORT BY RELATIVE VOLUME
        # ====================================================

        filtered = sorted(
            filtered,
            key=lambda x: x["Rel Vol"],
            reverse=True
        )

        # ====================================================
        # HEADER
        # ====================================================

        h1, h2, h3, h4, h5, h6 = st.columns(
            [
                0.70,
                0.95,
                0.90,
                1.00,
                0.90,
                0.75
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

        h6.markdown(
            "**Repeat**"
        )

        # ====================================================
        # ROWS
        # ====================================================

        for row in filtered:

            c1, c2, c3, c4, c5, c6 = st.columns(
                [
                    0.70,
                    0.95,
                    0.90,
                    1.00,
                    0.90,
                    0.75
                ]
            )

            # ------------------------------------------------
            # TIME
            # ------------------------------------------------

            c1.write(
                row["Time"]
            )

            # ------------------------------------------------
            # SYMBOL
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

            # ------------------------------------------------
            # LTP
            # ------------------------------------------------

            c3.write(
                f"{row['LTP']:.2f}"
            )

            # ------------------------------------------------
            # % CHANGE
            # ------------------------------------------------

            c4.write(
                f"{row['% Change']:.2f}%"
            )

            # ------------------------------------------------
            # RELATIVE VOLUME
            # ------------------------------------------------

            c5.write(
                f"{row['Rel Vol']:.1f}"
            )

            # ------------------------------------------------
            # REPEAT
            # ------------------------------------------------

            if row["Repeat"]:

                c6.markdown(
                    '<span class="repeat-signal">🔁</span>',
                    unsafe_allow_html=True
                )

            else:

                c6.write(
                    ""
                )

        # ====================================================
        # SUMMARY
        # ====================================================

        repeat_count = sum(
            1
            for row in filtered
            if row["Repeat"]
        )

        st.caption(
            f"{len(filtered)} stocks matched "
            f"from {len(data):,} scanned • "
            f"{repeat_count} with 🔁 repeat volume"
        )

    else:

        st.info(
            "Click 'Scan Russell 2000' to start."
        )


# ============================================================
# RIGHT — TRADINGVIEW
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

    exchange = (
        st.session_state
        .russell_exchanges
        .get(
            selected,
            "NASDAQ"
        )
    )

    # --------------------------------------------------------
    # TradingView symbol
    # --------------------------------------------------------

    if exchange == "NYSE":

        tv_symbol = (
            f"NYSE:{selected}"
        )

    elif exchange == "AMEX":

        tv_symbol = (
            f"AMEX:{selected}"
        )

    else:

        tv_symbol = (
            f"NASDAQ:{selected}"
        )

    # ========================================================
    # TRADINGVIEW HTML
    # ========================================================

    tradingview_html = f"""

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

                background: #131722;

            }}

            .tradingview-wrapper {{

                width: 100%;
                height: 100%;

                overflow: hidden;

            }}

            .tradingview-widget-container {{

                width: 100%;
                height: 100%;

                overflow: hidden;

            }}

            .tradingview-widget-container__widget {{

                width: 100%;
                height: calc(100% - 28px);

            }}

            .tradingview-widget-copyright {{

                height: 28px;

                line-height: 28px;

                font-size: 11px;

                text-align: center;

            }}

        </style>

    </head>

    <body>

        <div class="tradingview-wrapper">

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

                    "timezone": "America/New_York",

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

                    "popup_height": "700",

                    "calendar": false,

                    "details": false,

                    "hotlist": false,

                    "support_host":
                        "https://www.tradingview.com"

                }}

                </script>

            </div>

        </div>

    </body>

    </html>

    """

    components.html(
        tradingview_html,
        height=560,
        scrolling=False
    )
