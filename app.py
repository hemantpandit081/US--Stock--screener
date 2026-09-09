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
    page_title="US Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CONSTANTS
# ============================================================

SETTINGS_FILE = "scanner_settings.json"
NY_TZ = ZoneInfo("America/New_York")

DEFAULT_SETTINGS = {
    "min_price": 1.0,
    "max_price": 20.0,
    "min_volume": 100000,
    "min_rvol": 2.0,
    "min_change": 2.0,
    "max_stocks": 300,
    "repeat_tolerance": 0.90,
    "refresh_seconds": 60,
    "auto_scan": False,
}

# ============================================================
# PROFESSIONAL TRADING UI
# ============================================================

st.markdown(
    """
    <style>

    /* ======================================================
       GLOBAL
       ====================================================== */

    .stApp {
        background-color: #0b0f14;
        color: #e6edf3;
    }

    .block-container {
        max-width: 100%;
        padding-top: 0.65rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
        padding-bottom: 0.5rem;
    }

    header[data-testid="stHeader"] {
        background: #0b0f14;
    }

    /* ======================================================
       TOP BAR
       ====================================================== */

    .topbar {
        height: 46px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid #202832;
        margin-bottom: 8px;
    }

    .brand {
        font-size: 19px;
        font-weight: 700;
        color: #f0f3f6;
        letter-spacing: 0.2px;
    }

    .brand span {
        color: #58a6ff;
    }

    .market-status {
        font-size: 12px;
        font-weight: 600;
        color: #8b949e;
    }

    .market-open {
        color: #3fb950;
    }

    .market-closed {
        color: #8b949e;
    }

    /* ======================================================
       SCANNER PANEL
       ====================================================== */

    .scanner-panel {
        background: #0f141a;
        border: 1px solid #202832;
        border-radius: 6px;
        overflow: hidden;
    }

    .scanner-title-row {
        height: 43px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 12px;
        border-bottom: 1px solid #202832;
    }

    .scanner-title {
        font-size: 14px;
        font-weight: 700;
        color: #dce3ea;
    }

    .scanner-count {
        font-size: 11px;
        color: #7d8590;
    }

    /* ======================================================
       TABLE HEADER
       ====================================================== */

    .table-header {
        display: grid;
        grid-template-columns:
            55px
            minmax(95px, 1.3fr)
            72px
            82px
            65px;

        height: 31px;
        align-items: center;

        padding: 0 9px;

        background: #111820;
        border-bottom: 1px solid #202832;

        font-size: 10px;
        font-weight: 600;
        color: #737d89;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }

    /* ======================================================
       STOCK ROW
       ====================================================== */

    .stock-row {
        display: grid;
        grid-template-columns:
            55px
            minmax(95px, 1.3fr)
            72px
            82px
            65px;

        height: 38px;
        align-items: center;

        padding: 0 9px;

        border-bottom: 1px solid #171e26;

        font-size: 12px;
        color: #c9d1d9;

        transition: background 0.12s ease;
    }

    .stock-row:hover {
        background: #151c24;
    }

    .time-cell {
        color: #69737f;
        font-size: 10px;
    }

    .symbol-cell {
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .repeat-dot {
        color: #ffffff;
        font-size: 10px;
        width: 9px;
        display: inline-block;
    }

    .empty-dot {
        visibility: hidden;
    }

    .symbol-text {
        color: #f0f3f6;
        font-weight: 700;
        letter-spacing: 0.2px;
    }

    .price-cell {
        color: #dce3ea;
        font-variant-numeric: tabular-nums;
    }

    .change-positive {
        color: #3fb950;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }

    .change-negative {
        color: #f85149;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }

    .rvol-cell {
        color: #58a6ff;
        font-weight: 600;
        font-variant-numeric: tabular-nums;
    }

    /* ======================================================
       TRADINGVIEW PANEL
       ====================================================== */

    .chart-panel {
        background: #0f141a;
        border: 1px solid #202832;
        border-radius: 6px;
        overflow: hidden;
    }

    .chart-header {
        height: 43px;
        display: flex;
        align-items: center;
        padding: 0 13px;
        border-bottom: 1px solid #202832;
        color: #dce3ea;
        font-size: 14px;
        font-weight: 700;
    }

    .chart-symbol {
        color: #58a6ff;
        margin-left: 5px;
    }

    /* ======================================================
       BUTTONS
       ====================================================== */

    div.stButton > button {
        background: transparent;
        color: #f0f3f6;
        border: none;
        padding: 0;
        margin: 0;
        min-height: 0;
        height: 38px;
        width: 100%;
        text-align: left;
        font-size: 12px;
        font-weight: 700;
        border-radius: 0;
    }

    div.stButton > button:hover {
        background: #151c24;
        color: #58a6ff;
        border: none;
    }

    div.stButton > button:focus {
        box-shadow: none;
        border: none;
    }

    /* ======================================================
       SIDEBAR
       ====================================================== */

    section[data-testid="stSidebar"] {
        background: #0f141a;
        border-right: 1px solid #202832;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
    }

    /* ======================================================
       INPUTS
       ====================================================== */

    div[data-baseweb="input"] {
        background: #111820;
    }

    div[data-baseweb="select"] {
        background: #111820;
    }

    /* ======================================================
       INFO / EMPTY STATE
       ====================================================== */

    .empty-state {
        padding: 35px 15px;
        text-align: center;
        color: #687381;
        font-size: 12px;
    }

    .empty-state-title {
        color: #aab4bf;
        font-weight: 600;
        margin-bottom: 6px;
    }

    /* ======================================================
       FOOTER
       ====================================================== */

    .footer {
        text-align: right;
        color: #4f5965;
        font-size: 9px;
        padding-top: 5px;
    }

    </style>
    """,
    unsafe_allow_html=True
)

# ============================================================
# SETTINGS
# ============================================================

def load_settings():

    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS.copy()

    try:

        with open(SETTINGS_FILE, "r") as f:
            saved = json.load(f)

        settings = DEFAULT_SETTINGS.copy()
        settings.update(saved)

        return settings

    except Exception:

        return DEFAULT_SETTINGS.copy()


def save_settings(settings):

    try:

        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)

        return True

    except Exception as e:

        st.error(f"Unable to save settings: {e}")

        return False


# ============================================================
# SESSION STATE
# ============================================================

if "settings" not in st.session_state:
    st.session_state.settings = load_settings()

if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "AAPL"

if "scanner_data" not in st.session_state:
    st.session_state.scanner_data = pd.DataFrame()

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None

if "scanner_error" not in st.session_state:
    st.session_state.scanner_error = None


# ============================================================
# MARKET HOURS
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
# RUSSELL 2000
# ============================================================

@st.cache_data(ttl=86400)
def load_russell_2000():

    url = (
        "https://www.ishares.com/us/products/239710/"
        "ishares-russell-2000-etf/latest-holdings.csv"
    )

    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    lines = response.text.splitlines()

    header_index = None

    for i, line in enumerate(lines):

        if line.startswith("Ticker,"):
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
        io.StringIO(csv_text)
    )

    if "Ticker" not in df.columns:

        raise ValueError(
            "Ticker column not found."
        )

    symbols = (
        df["Ticker"]
        .astype(str)
        .str.strip()
    )

    symbols = symbols[
        ~symbols.isin(
            [
                "",
                "nan",
                "-",
                "USD",
                "CASH"
            ]
        )
    ]

    symbols = (
        symbols
        .str.replace(
            ".",
            "-",
            regex=False
        )
        .tolist()
    )

    return symbols


# ============================================================
# YAHOO DATA
# ============================================================

def get_symbol_data(df, symbol):

    if df is None or df.empty:
        return None

    try:

        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            level_values = (
                df.columns
                .get_level_values(1)
            )

            if symbol not in level_values:
                return None

            result = df.xs(
                symbol,
                axis=1,
                level=1
            )

        else:

            result = df

        result = result.dropna(
            how="all"
        )

        if result.empty:
            return None

        return result

    except Exception:

        return None


# ============================================================
# REPEAT DETECTION
# ============================================================

def detect_repeat(
    session_data,
    tolerance
):

    if (
        session_data is None
        or session_data.empty
    ):
        return False

    if "Volume" not in session_data.columns:
        return False

    volumes = pd.to_numeric(
        session_data["Volume"],
        errors="coerce"
    ).dropna()

    if len(volumes) < 2:
        return False

    current_volume = float(
        volumes.iloc[-1]
    )

    previous_volume = volumes.iloc[:-1]

    if previous_volume.empty:
        return False

    highest_previous = float(
        previous_volume.max()
    )

    if highest_previous <= 0:
        return False

    return (
        current_volume
        >= highest_previous * tolerance
    )


# ============================================================
# SCAN BATCH
# ============================================================

def scan_batch(symbols):

    results = []

    if not symbols:
        return results

    # --------------------------------------------------------
    # Intraday
    # --------------------------------------------------------

    try:

        intraday = yf.download(
            tickers=symbols,
            period="1d",
            interval="1m",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True
        )

    except Exception:

        return results

    # --------------------------------------------------------
    # Daily
    # --------------------------------------------------------

    try:

        daily = yf.download(
            tickers=symbols,
            period="20d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True
        )

    except Exception:

        daily = None

    # --------------------------------------------------------
    # Symbols
    # --------------------------------------------------------

    for symbol in symbols:

        try:

            intraday_data = get_symbol_data(
                intraday,
                symbol
            )

            if (
                intraday_data is None
                or intraday_data.empty
            ):
                continue

            # ------------------------------------------------
            # Close
            # ------------------------------------------------

            closes = pd.to_numeric(
                intraday_data["Close"],
                errors="coerce"
            ).dropna()

            if closes.empty:
                continue

            ltp = float(
                closes.iloc[-1]
            )

            if ltp <= 0:
                continue

            # ------------------------------------------------
            # Volume
            # ------------------------------------------------

            volumes = pd.to_numeric(
                intraday_data["Volume"],
                errors="coerce"
            ).fillna(0)

            session_volume = int(
                volumes.sum()
            )

            if session_volume <= 0:
                continue

            # ------------------------------------------------
            # Repeat
            # ------------------------------------------------

            repeat = detect_repeat(
                intraday_data,
                st.session_state.settings[
                    "repeat_tolerance"
                ]
            )

            # ------------------------------------------------
            # Daily data
            # ------------------------------------------------

            previous_close = None
            avg_daily_volume = None

            daily_data = get_symbol_data(
                daily,
                symbol
            )

            if (
                daily_data is not None
                and not daily_data.empty
            ):

                daily_closes = pd.to_numeric(
                    daily_data["Close"],
                    errors="coerce"
                ).dropna()

                daily_volumes = pd.to_numeric(
                    daily_data["Volume"],
                    errors="coerce"
                ).dropna()

                if len(daily_closes) >= 2:

                    previous_close = float(
                        daily_closes.iloc[-2]
                    )

                if len(daily_volumes) >= 6:

                    avg_daily_volume = float(
                        daily_volumes.iloc[-6:-1].mean()
                    )

            if (
                previous_close is None
                or previous_close <= 0
            ):
                continue

            if (
                avg_daily_volume is None
                or avg_daily_volume <= 0
            ):
                continue

            # ------------------------------------------------
            # Percentage
            # ------------------------------------------------

            pct_change = (
                (ltp - previous_close)
                / previous_close
                * 100
            )

            # ------------------------------------------------
            # Relative volume
            # ------------------------------------------------

            rel_volume = (
                session_volume
                / avg_daily_volume
            )

            # ------------------------------------------------
            # Time
            # ------------------------------------------------

            latest_time = (
                intraday_data.index[-1]
            )

            if latest_time.tzinfo is None:

                latest_time = latest_time.replace(
                    tzinfo=NY_TZ
                )

            else:

                latest_time = latest_time.astimezone(
                    NY_TZ
                )

            time_text = latest_time.strftime(
                "%H:%M"
            )

            # ------------------------------------------------
            # Result
            # ------------------------------------------------

            results.append(
                {
                    "Time": time_text,
                    "Symbol": symbol,
                    "LTP": round(
                        ltp,
                        2
                    ),
                    "% Change": round(
                        float(pct_change),
                        2
                    ),
                    "Rel Vol": round(
                        float(rel_volume),
                        1
                    ),
                    "Volume": session_volume,
                    "Repeat": bool(repeat)
                }
            )

        except Exception:

            continue

    return results


# ============================================================
# RUN SCANNER
# ============================================================

def run_scanner():

    settings = st.session_state.settings

    symbols = load_russell_2000()

    if not symbols:

        return pd.DataFrame()

    symbols = symbols[
        :int(settings["max_stocks"])
    ]

    batch_size = 50

    all_results = []

    total_batches = (
        len(symbols)
        + batch_size
        - 1
    ) // batch_size

    progress = st.progress(0)

    status = st.empty()

    for start in range(
        0,
        len(symbols),
        batch_size
    ):

        batch = symbols[
            start:start + batch_size
        ]

        batch_number = (
            start // batch_size
        ) + 1

        status.markdown(
            f"Scanning "
            f"**{batch_number}/{total_batches}**"
        )

        batch_results = scan_batch(
            batch
        )

        all_results.extend(
            batch_results
        )

        progress.progress(
            batch_number / total_batches
        )

    progress.empty()
    status.empty()

    if not all_results:

        return pd.DataFrame()

    df = pd.DataFrame(
        all_results
    )

    # --------------------------------------------------------
    # FILTERS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # SORT
    # --------------------------------------------------------

    df = df.sort_values(
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

    return df.reset_index(
        drop=True
    )


# ============================================================
# TRADINGVIEW
# ============================================================

def tradingview_chart(symbol):

    from streamlit.components.v1 import html

    tv_symbol = f"NASDAQ:{symbol}"

    chart_html = f"""
    <!DOCTYPE html>

    <html>

    <head>

        <meta charset="UTF-8">

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

            #tv_chart {{
                width: 100%;
                height: 100%;
            }}

        </style>

    </head>

    <body>

        <div id="tv_chart"></div>

        <script
            type="text/javascript"
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

                container_id: "tv_chart"

            }});

        </script>

    </body>

    </html>
    """

    html(
        chart_html,
        height=820,
        scrolling=False
    )


# ============================================================
# SIDEBAR FILTERS
# ============================================================

with st.sidebar:

    st.markdown(
        "## ⚙ Filters"
    )

    st.markdown("---")

    current = st.session_state.settings

    auto_scan = st.checkbox(
        "Automatic Scanner",
        value=bool(
            current["auto_scan"]
        )
    )

    refresh_seconds = st.number_input(
        "Refresh seconds",
        min_value=10,
        max_value=3600,
        value=int(
            current["refresh_seconds"]
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
            current["min_price"]
        ),
        step=0.50
    )

    max_price = st.number_input(
        "Maximum price",
        min_value=0.01,
        max_value=10000.0,
        value=float(
            current["max_price"]
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
            current["min_volume"]
        ),
        step=100000
    )

    min_rvol = st.number_input(
        "Minimum Rel Vol",
        min_value=0.1,
        max_value=1000.0,
        value=float(
            current["min_rvol"]
        ),
        step=0.5
    )

    min_change = st.number_input(
        "Minimum % Change",
        min_value=-100.0,
        max_value=1000.0,
        value=float(
            current["min_change"]
        ),
        step=0.5
    )

    max_stocks = st.number_input(
        "Maximum stocks to scan",
        min_value=10,
        max_value=2000,
        value=int(
            current["max_stocks"]
        ),
        step=50
    )

    st.markdown(
        "#### Repeat Volume"
    )

    repeat_percent = st.slider(
        "Repeat tolerance",
        min_value=50,
        max_value=100,
        value=int(
            current["repeat_tolerance"]
            * 100
        ),
        step=1
    )

    st.caption(
        "Repeat = current 1-minute volume "
        "is close to the previous highest "
        "1-minute volume."
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
            "max_stocks": max_stocks,
            "repeat_tolerance":
                repeat_percent / 100,
            "refresh_seconds":
                refresh_seconds,
            "auto_scan":
                auto_scan
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
            "max_stocks": max_stocks,
            "repeat_tolerance":
                repeat_percent / 100,
            "refresh_seconds":
                refresh_seconds,
            "auto_scan":
                auto_scan
        }

        save_settings(
            st.session_state.settings
        )

        try:

            with st.spinner(
                "Scanning US market..."
            ):

                result = run_scanner()

            st.session_state.scanner_data = result

            st.session_state.last_scan = (
                datetime.now(NY_TZ)
            )

            st.session_state.scanner_error = None

            if result.empty:

                st.warning(
                    "No stocks matched your filters."
                )

            else:

                st.success(
                    f"{len(result)} stocks found."
                )

        except Exception as e:

            st.session_state.scanner_error = str(e)

            st.error(
                "Scanner failed."
            )

            st.exception(e)


# ============================================================
# TOP BAR
# ============================================================

market_open = market_is_open()

if market_open:

    status_html = (
        '<span class="market-open">'
        '● US MARKET OPEN'
        '</span>'
    )

else:

    status_html = (
        '<span class="market-closed">'
        '● US MARKET CLOSED'
        '</span>'
    )

st.markdown(
    f"""
    <div class="topbar">

        <div class="brand">
            📈 <span>US Momentum</span> Scanner
        </div>

        <div class="market-status">
            {status_html}
        </div>

    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# MAIN COLUMNS
# ============================================================

scanner_col, chart_col = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT — SCANNER
# ============================================================

with scanner_col:

    data = st.session_state.scanner_data

    count = (
        len(data)
        if not data.empty
        else 0
    )

    st.markdown(
        f"""
        <div class="scanner-panel">

            <div class="scanner-title-row">

                <div class="scanner-title">
                    Momentum Scanner
                </div>

                <div class="scanner-count">
                    {count} stocks
                </div>

            </div>

            <div class="table-header">

                <div>Time</div>
                <div>Symbol</div>
                <div>LTP</div>
                <div>Change</div>
                <div>RVOL</div>

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # EMPTY STATE
    # --------------------------------------------------------

    if data.empty:

        st.markdown(
            """
            <div class="empty-state">

                <div class="empty-state-title">
                    Scanner ready
                </div>

                Click
                <b>Scan Now</b>
                in Filters to start.

            </div>
            """,
            unsafe_allow_html=True
        )

    # --------------------------------------------------------
    # STOCK LIST
    # --------------------------------------------------------

    else:

        for index, row in data.iterrows():

            symbol = str(
                row["Symbol"]
            )

            repeat = bool(
                row["Repeat"]
            )

            change = float(
                row["% Change"]
            )

            # -----------------------------------------------
            # Stock row container
            # -----------------------------------------------

            row_col1, row_col2 = st.columns(
                [1.45, 3.55],
                gap="small"
            )

            with row_col1:

                st.markdown(
                    f"""
                    <div class="stock-row">

                        <div class="time-cell">
                            {row["Time"]}
                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with row_col2:

                ticker_clicked = st.button(
                    symbol,
                    key=f"ticker_{symbol}_{index}",
                    use_container_width=True
                )

                if ticker_clicked:

                    st.session_state.selected_ticker = (
                        symbol
                    )

                    st.rerun()

                # Overlay information beside button
                st.markdown(
                    f"""
                    <div style="
                        margin-top:-38px;
                        height:38px;
                        display:grid;
                        grid-template-columns:
                            minmax(80px,1.3fr)
                            72px
                            82px
                            65px;
                        align-items:center;
                        pointer-events:none;
                    ">

                        <div class="symbol-cell">

                            <span class="
                                repeat-dot
                                {'empty-dot' if not repeat else ''}
                            ">
                                ●
                            </span>

                        </div>

                        <div class="price-cell">
                            ${float(row["LTP"]):.2f}
                        </div>

                        <div class="
                            {'change-positive'
                            if change >= 0
                            else 'change-negative'}
                        ">
                            {change:+.2f}%
                        </div>

                        <div class="rvol-cell">
                            {float(row["Rel Vol"]):.1f}
                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )


# ============================================================
# RIGHT — TRADINGVIEW
# ============================================================

with chart_col:

    selected = (
        st.session_state.selected_ticker
    )

    st.markdown(
        f"""
        <div class="chart-panel">

            <div class="chart-header">

                TradingView

                <span class="chart-symbol">
                    {selected}
                </span>

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    tradingview_chart(
        selected
    )


# ============================================================
# FOOTER
# ============================================================

last_scan = st.session_state.last_scan

if last_scan:

    last_scan_text = (
        last_scan.strftime(
            "%H:%M:%S"
        )
    )

else:

    last_scan_text = "--"

st.markdown(
    f"""
    <div class="footer">
        Last scan: {last_scan_text}
        &nbsp; | &nbsp;
        1-minute scanner
        &nbsp; | &nbsp;
        Yahoo Finance
    </div>
    """,
    unsafe_allow_html=True
)
