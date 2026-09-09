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
    gap: 0.35rem !important;
}

div[data-testid="stVerticalBlock"] {
    gap: 0.25rem;
}

.repeat-signal {
    font-size: 17px;
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
    "repeat_tolerance": 0.90,
    "refresh_seconds": 60,
    "auto_scan": True
}


# ============================================================
# RUSSELL 2000
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
# SESSION STATE
# ============================================================

if "settings_loaded" not in st.session_state:

    saved = load_saved_settings()

    st.session_state.min_price = saved["min_price"]
    st.session_state.max_price = saved["max_price"]
    st.session_state.min_volume = saved["min_volume"]
    st.session_state.min_rvol = saved["min_rvol"]
    st.session_state.min_change = saved["min_change"]
    st.session_state.max_stocks = saved["max_stocks"]
    st.session_state.repeat_tolerance = saved[
        "repeat_tolerance"
    ]
    st.session_state.refresh_seconds = saved[
        "refresh_seconds"
    ]
    st.session_state.auto_scan = saved[
        "auto_scan"
    ]

    st.session_state.settings_loaded = True


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

    response = requests.get(
        RUSSELL_2000_URL,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=30
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
            "Could not find Russell 2000 holdings header."
        )

    csv_text = "\n".join(
        lines[header_index:]
    )

    df = pd.read_csv(
        StringIO(csv_text)
    )

    # --------------------------------------------------------
    # Equity only
    # --------------------------------------------------------

    df = df[
        df["Asset Class"]
        .astype(str)
        .str.lower()
        .eq("equity")
    ].copy()

    # --------------------------------------------------------
    # United States only
    # --------------------------------------------------------

    df = df[
        df["Location"]
        .astype(str)
        .str.contains(
            "United States",
            case=False,
            na=False
        )
    ].copy()

    # --------------------------------------------------------
    # Clean ticker
    # --------------------------------------------------------

    df["Ticker"] = (
        df["Ticker"]
        .astype(str)
        .str.strip()
        .str.replace(
            ".",
            "-",
            regex=False
        )
    )

    df = df[
        df["Ticker"].notna()
        & (df["Ticker"] != "")
        & (df["Ticker"] != "nan")
    ]

    df = df.drop_duplicates(
        subset=["Ticker"]
    )

    # --------------------------------------------------------
    # Exchange map
    # --------------------------------------------------------

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

    return (
        df["Ticker"].tolist(),
        exchange_map
    )


# ============================================================
# INITIALISE RUSSELL
# ============================================================

if not st.session_state.russell_loaded:

    try:

        (
            symbols,
            exchanges
        ) = load_russell_2000()

        st.session_state.russell_symbols = symbols
        st.session_state.russell_exchanges = exchanges
        st.session_state.russell_loaded = True

    except Exception as e:

        st.error(
            f"Russell 2000 loading error: {e}"
        )


# ============================================================
# GET SYMBOL DATA FROM YFINANCE
# ============================================================

def get_symbol_data(
    data,
    symbol
):

    try:

        if len(
            data.columns
        ) == 0:

            return None

        if not isinstance(
            data.columns,
            pd.MultiIndex
        ):

            return data.copy()

        level0 = data.columns.get_level_values(0)

        level1 = data.columns.get_level_values(1)

        # Standard group_by="ticker"
        if symbol in level0:

            return data[symbol].copy()

        # Alternative layout
        if symbol in level1:

            return data.xs(
                symbol,
                axis=1,
                level=1
            ).copy()

    except Exception:

        return None

    return None


# ============================================================
# REPEAT VOLUME
# ============================================================

def detect_repeat(
    session_data,
    tolerance
):

    if session_data.empty:
        return False, 0, 0

    if "Volume" not in session_data.columns:
        return False, 0, 0

    volumes = pd.to_numeric(
        session_data["Volume"],
        errors="coerce"
    ).fillna(0)

    volumes = [
        float(v)
        for v in volumes
        if float(v) > 0
    ]

    if len(volumes) < 2:

        return False, 0, 0

    current_volume = volumes[-1]

    previous_volumes = volumes[:-1]

    if not previous_volumes:

        return False, 0, 0

    # --------------------------------------------------------
    # Previous highest 5-minute volume
    # --------------------------------------------------------

    previous_spike = max(
        previous_volumes
    )

    threshold = (
        previous_spike
        * tolerance
    )

    repeat = (
        current_volume
        >= threshold
    )

    return (
        repeat,
        current_volume,
        previous_spike
    )


# ============================================================
# SCAN STOCK BATCH
# ============================================================

def scan_batch(symbols):

    results = []

    if not symbols:
        return results

    # ========================================================
    # 5 MINUTE DATA
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
            f"Intraday error: {e}"
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
            f"Daily error: {e}"
        )

        return results

    # ========================================================
    # PROCESS STOCKS
    # ========================================================

    for symbol in symbols:

        try:

            symbol_intraday = get_symbol_data(
                intraday,
                symbol
            )

            if symbol_intraday is None:
                continue

            if symbol_intraday.empty:
                continue

            if (
                "Close" not in symbol_intraday.columns
                or
                "Volume" not in symbol_intraday.columns
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
            # Latest session
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
            # Session volume
            # ------------------------------------------------

            session_volume = float(
                session_data[
                    "Volume"
                ].sum()
            )

            # ------------------------------------------------
            # Current 5-minute volume
            # ------------------------------------------------

            current_5m_volume = float(
                session_data[
                    "Volume"
                ].iloc[-1]
            )

            # =================================================
            # REPEAT
            # =================================================

            (
                repeat,
                current_volume,
                previous_spike
            ) = detect_repeat(
                session_data,
                st.session_state.repeat_tolerance
            )

            # =================================================
            # DAILY
            # =================================================

            symbol_daily = get_symbol_data(
                daily,
                symbol
            )

            if symbol_daily is None:
                continue

            if symbol_daily.empty:
                continue

            if (
                "Close" not in symbol_daily.columns
                or
                "Volume" not in symbol_daily.columns
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

            # ------------------------------------------------
            # Previous close
            # ------------------------------------------------

            previous_close = float(
                symbol_daily[
                    "Close"
                ].iloc[-2]
            )

            if previous_close <= 0:
                continue

            # ------------------------------------------------
            # % Change
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
            # Previous 5 days average volume
            # ------------------------------------------------

            previous_volumes = (
                symbol_daily[
                    "Volume"
                ].iloc[-6:-1]
            )

            average_daily_volume = float(
                previous_volumes.mean()
            )

            # ------------------------------------------------
            # Rel Vol
            # ------------------------------------------------

            if average_daily_volume > 0:

                relative_volume = (
                    session_volume
                    / average_daily_volume
                )

            else:

                relative_volume = 0

            # ------------------------------------------------
            # Time
            # ------------------------------------------------

            timestamp = (
                session_data.index[-1]
            )

            try:

                timestamp = (
                    timestamp
                    .tz_convert(
                        "America/New_York"
                    )
                )

            except Exception:

                pass

            time_string = timestamp.strftime(
                "%H:%M"
            )

            # ------------------------------------------------
            # Store result
            # ------------------------------------------------

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
                    repeat,

                "Previous Spike":
                    previous_spike

            })

        except Exception as e:

            print(
                f"{symbol}: {e}"
            )

    return results


# ============================================================
# COMPLETE SCAN
# ============================================================

def run_scanner():

    symbols = (
        st.session_state.russell_symbols
    )

    if not symbols:
        return []

    # --------------------------------------------------------
    # Number of stocks
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
        symbols[
            i:i + batch_size
        ]
        for i in range(
            0,
            len(symbols),
            batch_size
        )
    ]

    all_results = []

    total = len(symbols)

    completed = 0

    progress = st.progress(0)

    status = st.empty()

    # ========================================================
    # BATCHES
    # ========================================================

    for batch_number, batch in enumerate(
        batches,
        start=1
    ):

        status.text(
            f"Scanning Russell 2000 "
            f"• Batch {batch_number}/{len(batches)} "
            f"• {completed}/{total}"
        )

        batch_results = scan_batch(
            batch
        )

        all_results.extend(
            batch_results
        )

        completed += len(batch)

        progress.progress(
            completed / total
        )

    progress.empty()
    status.empty()

    return all_results


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "Scanner Controls"
    )

    st.write(
        "Universe: **Russell 2000**"
    )

    st.caption(
        f"{len(st.session_state.russell_symbols):,} "
        "stocks loaded"
    )

    # ========================================================
    # AUTO SCAN
    # ========================================================

    st.session_state.auto_scan = st.toggle(
        "🔄 Automatic Scanner",
        value=st.session_state.auto_scan
    )

    # ========================================================
    # REFRESH
    # ========================================================

    st.session_state.refresh_seconds = st.selectbox(
        "Refresh Every",
        options=[
            30,
            60,
            90,
            120,
            180,
            300
        ],
        index=[
            30,
            60,
            90,
            120,
            180,
            300
        ].index(
            int(
                st.session_state.refresh_seconds
            )
        ),
        format_func=lambda x:
            f"{x} seconds"
    )

    # ========================================================
    # STOCK COUNT
    # ========================================================

    st.session_state.max_stocks = st.number_input(
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

    st.caption(
        "300 is recommended initially."
    )

    # ========================================================
    # PRICE
    # ========================================================

    st.session_state.min_price = st.number_input(
        "Minimum Price",
        min_value=0.0,
        value=float(
            st.session_state.min_price
        ),
        step=0.50
    )

    st.session_state.max_price = st.number_input(
        "Maximum Price",
        min_value=0.0,
        value=float(
            st.session_state.max_price
        ),
        step=0.50
    )

    # ========================================================
    # VOLUME
    # ========================================================

    st.session_state.min_volume = st.number_input(
        "Minimum Volume",
        min_value=0,
        value=int(
            st.session_state.min_volume
        ),
        step=10000
    )

    # ========================================================
    # RVOL
    # ========================================================

    st.session_state.min_rvol = st.number_input(
        "Minimum Rel Vol",
        min_value=0.0,
        value=float(
            st.session_state.min_rvol
        ),
        step=0.5
    )

    # ========================================================
    # % CHANGE
    # ========================================================

    st.session_state.min_change = st.number_input(
        "Minimum % Change",
        min_value=-100.0,
        value=float(
            st.session_state.min_change
        ),
        step=0.5
    )

    # ========================================================
    # REPEAT
    # ========================================================

    repeat_percent = st.slider(
        "🔁 Repeat Threshold",
        min_value=50,
        max_value=100,
        value=int(
            st.session_state.repeat_tolerance
            * 100
        ),
        step=5
    )

    st.session_state.repeat_tolerance = (
        repeat_percent / 100
    )

    st.caption(
        f"🔁 = current 5-minute volume is "
        f"{repeat_percent}% or more of the "
        f"previous volume spike."
    )

    st.markdown("---")

    # ========================================================
    # SAVE
    # ========================================================

    if st.button(
        "💾 Save Settings",
        use_container_width=True
    ):

        settings = {

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
                st.session_state.repeat_tolerance,

            "refresh_seconds":
                st.session_state.refresh_seconds,

            "auto_scan":
                st.session_state.auto_scan

        }

        if save_settings(settings):

            st.success(
                "Settings saved."
            )

    # ========================================================
    # MANUAL SCAN
    # ========================================================

    manual_scan = st.button(
        "🔍 Scan Now",
        use_container_width=True,
        type="primary"
    )


# ============================================================
# MARKET STATUS
# ============================================================

market_time = get_market_time()

market_open = market_is_open()

if market_open:

    st.success(
        "🟢 US MARKET OPEN  •  "
        + market_time.strftime(
            "%H:%M:%S"
        )
        + " ET"
    )

else:

    st.info(
        "🔴 US MARKET CLOSED  •  "
        + market_time.strftime(
            "%H:%M:%S"
        )
        + " ET"
    )


# ============================================================
# AUTOMATIC SCANNER FRAGMENT
# ============================================================

if (
    st.session_state.auto_scan
    and market_open
):

    run_every = (
        f"{int(st.session_state.refresh_seconds)}s"
    )

else:

    run_every = None


@st.fragment(run_every=run_every)
def automatic_scanner():

    # ========================================================
    # AUTOMATIC SCAN
    # ========================================================

    should_scan = False

    if market_is_open():

        should_scan = True

    # Manual button can also trigger scan.
    if manual_scan:

        should_scan = True

    if should_scan:

        with st.spinner(
            "Updating Russell 2000..."
        ):

            new_data = run_scanner()

            if new_data:

                st.session_state.scanner_data = (
                    new_data
                )

                st.session_state.last_scan_time = (
                    datetime.now().strftime(
                        "%H:%M:%S"
                    )
                )

    # ========================================================
    # LAST UPDATE
    # ========================================================

    if st.session_state.last_scan_time:

        st.caption(
            "Last update: "
            + st.session_state.last_scan_time
            + " ET"
        )

    # ========================================================
    # MAIN COLUMNS
    # ========================================================

    scanner_col, chart_col = st.columns(
        [35, 65],
        gap="small"
    )

    # ========================================================
    # SCANNER
    # ========================================================

    with scanner_col:

        st.markdown(
            "### Scanner"
        )

        data = (
            st.session_state.scanner_data
        )

        if data:

            filtered = []

            # ------------------------------------------------
            # FILTERS
            # ------------------------------------------------

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

            # ------------------------------------------------
            # SORT
            # ------------------------------------------------

            filtered.sort(
                key=lambda x:
                    x["Rel Vol"],
                reverse=True
            )

            # ------------------------------------------------
            # HEADER
            # ------------------------------------------------

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

            h1.markdown("**Time**")
            h2.markdown("**Symbol**")
            h3.markdown("**LTP**")
            h4.markdown("**% Change**")
            h5.markdown("**Rel Vol**")
            h6.markdown("**Repeat**")

            # ------------------------------------------------
            # ROWS
            # ------------------------------------------------

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

                c1.write(
                    row["Time"]
                )

                # --------------------------------------------
                # TICKER BUTTON
                # --------------------------------------------

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

                    # Full rerun so TradingView updates.
                    st.rerun()

                c3.write(
                    f"{row['LTP']:.2f}"
                )

                c4.write(
                    f"{row['% Change']:.2f}%"
                )

                c5.write(
                    f"{row['Rel Vol']:.1f}"
                )

                # --------------------------------------------
                # REPEAT
                # --------------------------------------------

                if row["Repeat"]:

                    c6.markdown(
                        '<span class="repeat-signal">🔁</span>',
                        unsafe_allow_html=True
                    )

                else:

                    c6.write("")

            # ------------------------------------------------
            # SUMMARY
            # ------------------------------------------------

            repeat_count = sum(
                1
                for row in filtered
                if row["Repeat"]
            )

            st.caption(
                f"{len(filtered)} stocks matched "
                f"• {repeat_count} 🔁 repeat-volume stocks"
            )

        else:

            st.info(
                "Waiting for automatic scanner..."
            )

    # ========================================================
    # TRADINGVIEW
    # ========================================================

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

        # ====================================================
        # TRADINGVIEW
        # ====================================================

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


# ============================================================
# START SCANNER
# ============================================================

automatic_scanner()
