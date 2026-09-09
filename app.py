import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, time
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components


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
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 0.25rem;
        padding-bottom: 0.25rem;
        padding-left: 0.30rem;
        padding-right: 0.30rem;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header {
        visibility: hidden;
    }

    .scanner-title {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 8px;
    }

    .repeat-square {
        font-size: 17px;
        font-weight: 900;
        color: white;
        line-height: 1;
        text-align: center;
        padding-top: 5px;
    }

    .stock-time {
        font-size: 10px;
        white-space: nowrap;
        padding-top: 5px;
    }

    .stock-price {
        font-size: 11px;
        font-weight: 600;
        padding-top: 5px;
    }

    .stock-change {
        font-size: 11px;
        font-weight: 600;
        padding-top: 5px;
    }

    .stock-rvol {
        font-size: 11px;
        font-weight: 700;
        padding-top: 5px;
    }

    div[data-testid="stButton"] button {
        min-height: 25px;
        height: 25px;
        padding: 0px 3px;
        font-size: 11px;
        font-weight: 700;
    }

    div[data-testid="stPopover"] button {
        min-height: 30px;
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
    "repeat_tolerance": 90,
    "refresh_seconds": 60,
    "auto_scanner": True,
}


# ============================================================
# SESSION STATE
# ============================================================

if "settings" not in st.session_state:
    st.session_state.settings = DEFAULT_SETTINGS.copy()

if "scan_results" not in st.session_state:
    st.session_state.scan_results = None

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = None

if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None


# ============================================================
# SETTINGS
# ============================================================

def load_settings():

    s = st.session_state.settings

    try:
        min_price = float(s.get("min_price", 1.0))
    except Exception:
        min_price = 1.0

    try:
        max_price = float(s.get("max_price", 20.0))
    except Exception:
        max_price = 20.0

    try:
        min_volume = int(s.get("min_volume", 100000))
    except Exception:
        min_volume = 100000

    try:
        min_rvol = float(s.get("min_rvol", 2.0))
    except Exception:
        min_rvol = 2.0

    try:
        min_change = float(s.get("min_change", 2.0))
    except Exception:
        min_change = 2.0

    try:
        max_stocks = int(s.get("max_stocks", 300))
    except Exception:
        max_stocks = 300

    try:
        repeat_tolerance = float(
            s.get("repeat_tolerance", 90)
        )
    except Exception:
        repeat_tolerance = 90

    try:
        refresh_seconds = int(
            s.get("refresh_seconds", 60)
        )
    except Exception:
        refresh_seconds = 60

    auto_scanner = bool(
        s.get("auto_scanner", True)
    )

    min_price = max(0.01, min_price)

    max_price = max(
        min_price,
        max_price
    )

    min_volume = max(
        0,
        min_volume
    )

    min_rvol = max(
        0.1,
        min_rvol
    )

    max_stocks = max(
        1,
        max_stocks
    )

    repeat_tolerance = min(
        100,
        max(
            1,
            repeat_tolerance
        )
    )

    refresh_seconds = max(
        10,
        refresh_seconds
    )

    clean = {
        "min_price": min_price,
        "max_price": max_price,
        "min_volume": min_volume,
        "min_rvol": min_rvol,
        "min_change": min_change,
        "max_stocks": max_stocks,
        "repeat_tolerance": repeat_tolerance,
        "refresh_seconds": refresh_seconds,
        "auto_scanner": auto_scanner,
    }

    st.session_state.settings = clean

    return clean


# ============================================================
# RUSSELL 2000 SYMBOLS
# ============================================================

@st.cache_data(ttl=86400)
def load_russell_2000():

    url = (
        "https://www.ishares.com/us/products/"
        "239771/ishares-russell-2000-etf/"
        "1467271812596.ajax?"
        "fileType=csv&fileName=IWM_holdings&dataType=fund"
    )

    try:

        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        if response.status_code == 200:

            lines = response.text.splitlines()

            start = None

            for i, line in enumerate(lines):

                if "Ticker" in line and "Name" in line:

                    start = i
                    break

            if start is not None:

                from io import StringIO

                csv_text = "\n".join(
                    lines[start:]
                )

                df = pd.read_csv(
                    StringIO(csv_text)
                )

                ticker_column = None

                for column in [
                    "Ticker",
                    "Ticker Symbol",
                    "Symbol"
                ]:

                    if column in df.columns:

                        ticker_column = column
                        break

                if ticker_column:

                    symbols = (
                        df[ticker_column]
                        .dropna()
                        .astype(str)
                        .str.strip()
                        .tolist()
                    )

                    cleaned = []

                    for symbol in symbols:

                        if not symbol:
                            continue

                        if symbol == "nan":
                            continue

                        if "." in symbol:
                            continue

                        cleaned.append(symbol)

                    if len(cleaned) > 100:

                        return list(
                            dict.fromkeys(cleaned)
                        )

    except Exception:
        pass


    # --------------------------------------------------------
    # FALLBACK SYMBOLS
    # --------------------------------------------------------

    return [
        "AAL",
        "AAOI",
        "ABCL",
        "ABEO",
        "ACHR",
        "ACMR",
        "ADMA",
        "AEHR",
        "AI",
        "AKBA",
        "ALLO",
        "AMRX",
        "APLD",
        "APPS",
        "ARLO",
        "ARQQ",
        "ARRY",
        "ASTS",
        "ATNF",
        "ATOS",
        "AUR",
        "BBAI",
        "BBIO",
        "BCRX",
        "BE",
        "BILI",
        "BITF",
        "BLBD",
        "BLDE",
        "BMBL",
        "BMRN",
        "BNGO",
        "BTBT",
        "BTDR",
        "CABA",
        "CAN",
        "CARG",
        "CDE",
        "CELH",
        "CHPT",
        "CLSK",
        "CMRX",
        "COIN",
        "COMM",
        "CRDO",
        "CRK",
        "CRNC",
        "CRSP",
        "CVNA",
        "CYTK",
        "DAVE",
        "DNA",
        "DNN",
        "DOCS",
        "DLO",
        "EDIT",
        "ENVX",
        "EOSE",
        "EVGO",
        "EXAS",
        "FATE",
        "FCEL",
        "FOLD",
        "FUBO",
        "GCT",
        "GDRX",
        "GEVO",
        "GME",
        "GOEV",
        "GOSS",
        "GRAB",
        "HIMS",
        "HIVE",
        "HOOD",
        "IONQ",
        "JOBY",
        "LCID",
        "LUMN",
        "LUNR",
        "MARA",
        "MAXN",
        "MCRB",
        "MGNI",
        "MNMD",
        "MPLN",
        "MVIS",
        "NEGG",
        "NIO",
        "NKLA",
        "NNDM",
        "NU",
        "NVAX",
        "OCGN",
        "OPEN",
        "OPRX",
        "ORGN",
        "PACB",
        "PAGS",
        "PLTR",
        "PLUG",
        "POET",
        "PRCH",
        "PRME",
        "PSNY",
        "PTON",
        "QBTS",
        "QUBT",
        "RANI",
        "RDFN",
        "REKR",
        "RIOT",
        "RKLB",
        "RIVN",
        "ROIV",
        "RXRX",
        "SENS",
        "SERV",
        "SIRI",
        "SLDP",
        "SLNO",
        "SOUN",
        "SPCE",
        "SST",
        "STNE",
        "TELL",
        "TMC",
        "TMDX",
        "TOST",
        "TQQQ",
        "TRIB",
        "TSLA",
        "TUP",
        "TWST",
        "UAL",
        "UPST",
        "URG",
        "VERU",
        "VKTX",
        "VRDN",
        "WBD",
        "WKHS",
        "WOLF",
        "XPEV",
        "ZIM"
    ]


# ============================================================
# GET SYMBOL DATA
# ============================================================

def get_symbol_data(df, symbol):

    if df is None or df.empty:
        return None

    try:

        if isinstance(
            df.columns,
            pd.MultiIndex
        ):

            level0 = df.columns.get_level_values(0)

            level1 = df.columns.get_level_values(1)

            if symbol in level0:

                return df[symbol].copy()

            if symbol in level1:

                return df.xs(
                    symbol,
                    axis=1,
                    level=1
                ).copy()

        return df.copy()

    except Exception:

        return None


# ============================================================
# REPEAT DETECTION
# ============================================================

def detect_repeat(
    intraday_df,
    tolerance
):

    if intraday_df is None:
        return False

    if intraday_df.empty:
        return False

    if "Volume" not in intraday_df.columns:
        return False

    try:

        volumes = pd.to_numeric(
            intraday_df["Volume"],
            errors="coerce"
        ).dropna()

        volumes = volumes[
            volumes > 0
        ]

        if len(volumes) < 2:
            return False

        current_volume = float(
            volumes.iloc[-1]
        )

        previous = volumes.iloc[:-1]

        if previous.empty:
            return False

        previous_high = float(
            previous.max()
        )

        if previous_high <= 0:
            return False

        threshold = (
            previous_high
            * tolerance
            / 100
        )

        return current_volume >= threshold

    except Exception:

        return False


# ============================================================
# SCAN BATCH
# ============================================================

def scan_batch(
    symbols,
    settings
):

    results = []

    if not symbols:
        return results

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

        intraday = None


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

        daily = None


    if intraday is None:
        return results

    if intraday.empty:
        return results


    for symbol in symbols:

        try:

            intra_df = get_symbol_data(
                intraday,
                symbol
            )

            daily_df = get_symbol_data(
                daily,
                symbol
            )

            if intra_df is None:
                continue

            if intra_df.empty:
                continue

            if "Close" not in intra_df.columns:
                continue

            if "Volume" not in intra_df.columns:
                continue


            # ------------------------------------------------
            # CLEAN DATA
            # ------------------------------------------------

            intra_df = intra_df.copy()

            intra_df["Close"] = pd.to_numeric(
                intra_df["Close"],
                errors="coerce"
            )

            intra_df["Volume"] = pd.to_numeric(
                intra_df["Volume"],
                errors="coerce"
            )

            intra_df = intra_df.dropna(
                subset=["Close"]
            )

            if intra_df.empty:
                continue


            # ------------------------------------------------
            # LTP
            # ------------------------------------------------

            ltp = float(
                intra_df["Close"].iloc[-1]
            )

            if not np.isfinite(ltp):
                continue


            # ------------------------------------------------
            # PRICE FILTER
            # ------------------------------------------------

            if ltp < settings["min_price"]:
                continue

            if ltp > settings["max_price"]:
                continue


            # ------------------------------------------------
            # SESSION VOLUME
            # ------------------------------------------------

            session_volume = float(
                intra_df["Volume"]
                .fillna(0)
                .sum()
            )

            if session_volume < settings["min_volume"]:
                continue


            # ------------------------------------------------
            # PREVIOUS CLOSE
            # ------------------------------------------------

            previous_close = None

            if daily_df is not None:

                if not daily_df.empty:

                    if "Close" in daily_df.columns:

                        closes = pd.to_numeric(
                            daily_df["Close"],
                            errors="coerce"
                        ).dropna()

                        if len(closes) >= 2:

                            previous_close = float(
                                closes.iloc[-2]
                            )

            if previous_close is None:
                continue

            if previous_close <= 0:
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

            if (
                percent_change
                < settings["min_change"]
            ):
                continue


            # ------------------------------------------------
            # RELATIVE VOLUME
            # ------------------------------------------------

            rvol = 0.0

            if daily_df is not None:

                if not daily_df.empty:

                    if "Volume" in daily_df.columns:

                        daily_volumes = pd.to_numeric(
                            daily_df["Volume"],
                            errors="coerce"
                        ).dropna()

                        if len(daily_volumes) >= 2:

                            previous_days = (
                                daily_volumes
                                .iloc[:-1]
                                .tail(5)
                            )

                            if not previous_days.empty:

                                average_volume = float(
                                    previous_days.mean()
                                )

                                if average_volume > 0:

                                    rvol = (
                                        session_volume
                                        / average_volume
                                    )

            if rvol < settings["min_rvol"]:
                continue


            # ------------------------------------------------
            # REPEAT
            # ------------------------------------------------

            repeat = detect_repeat(
                intra_df,
                settings["repeat_tolerance"]
            )


            # ------------------------------------------------
            # TIME
            # ------------------------------------------------

            timestamp = intra_df.index[-1]

            try:

                if timestamp.tzinfo is None:

                    timestamp = timestamp.tz_localize(
                        "America/New_York"
                    )

                else:

                    timestamp = timestamp.tz_convert(
                        "America/New_York"
                    )

                display_time = timestamp.strftime(
                    "%H:%M"
                )

            except Exception:

                display_time = datetime.now(
                    ZoneInfo("America/New_York")
                ).strftime("%H:%M")


            # ------------------------------------------------
            # ADD RESULT
            # ------------------------------------------------

            results.append(
                {
                    "Time": display_time,
                    "Symbol": symbol,
                    "LTP": ltp,
                    "% Change": percent_change,
                    "Rel Vol": rvol,
                    "Volume": session_volume,
                    "Repeat": repeat
                }
            )

        except Exception:

            continue


    return results


# ============================================================
# RUN SCANNER
# ============================================================

def run_scanner():

    settings = load_settings()

    symbols = load_russell_2000()

    symbols = symbols[
        :settings["max_stocks"]
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

        batch_results = scan_batch(
            batch,
            settings
        )

        all_results.extend(
            batch_results
        )


    if all_results:

        df = pd.DataFrame(
            all_results
        )

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

        df = df.reset_index(
            drop=True
        )

    else:

        df = pd.DataFrame(
            columns=[
                "Time",
                "Symbol",
                "LTP",
                "% Change",
                "Rel Vol",
                "Volume",
                "Repeat"
            ]
        )


    st.session_state.scan_results = df

    st.session_state.last_scan_time = datetime.now(
        ZoneInfo("America/New_York")
    )


# ============================================================
# TRADINGVIEW
# ============================================================

def show_tradingview(symbol):

    symbol = str(
        symbol
    ).upper().strip()

    # TradingView Advanced Chart
    # 1-minute candles
    # Drawing toolbar enabled

    html = f"""
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
                background: #131722;
            }}

            #tv_chart {{
                width: 100%;
                height: 100%;
            }}

        </style>

    </head>

    <body>

        <div
            id="tv_chart"
        ></div>

        <script
            type="text/javascript"
            src="https://s3.tradingview.com/tv.js">
        </script>

        <script>

            new TradingView.widget({{

                "container_id": "tv_chart",

                "width": "100%",

                "height": "100%",

                "symbol": "NASDAQ:{symbol}",

                "interval": "1",

                "timezone": "America/New_York",

                "theme": "dark",

                "style": "1",

                "locale": "en",

                "enable_publishing": false,

                "allow_symbol_change": true,

                "withdateranges": true,

                "hide_side_toolbar": false,

                "hide_top_toolbar": false,

                "hide_legend": false,

                "hide_volume": false,

                "save_image": true,

                "calendar": false,

                "studies": [],

                "support_host": "https://www.tradingview.com"

            }});

        </script>

    </body>

    </html>
    """

    components.html(
        html,
        height=720,
        scrolling=False
    )


# ============================================================
# MARKET HOURS
# ============================================================

def regular_market_hours():

    now = datetime.now(
        ZoneInfo("America/New_York")
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
# FILTER SETTINGS
# ============================================================

def show_filters():

    current = load_settings()

    with st.popover("⚙ Filters"):

        st.markdown(
            "### Scanner Filters"
        )

        col1, col2 = st.columns(2)


        with col1:

            min_price = st.number_input(
                "Min price",
                min_value=0.01,
                value=float(
                    current["min_price"]
                ),
                step=0.10,
                format="%.2f"
            )

            max_price = st.number_input(
                "Max price",
                min_value=0.01,
                value=float(
                    current["max_price"]
                ),
                step=0.50,
                format="%.2f"
            )

            min_volume = st.number_input(
                "Min volume",
                min_value=0,
                value=int(
                    current["min_volume"]
                ),
                step=10000
            )

            min_rvol = st.number_input(
                "Min Rel Vol",
                min_value=0.1,
                value=float(
                    current["min_rvol"]
                ),
                step=0.5,
                format="%.1f"
            )


        with col2:

            min_change = st.number_input(
                "Min % change",
                value=float(
                    current["min_change"]
                ),
                step=0.5,
                format="%.1f"
            )

            max_stocks = st.number_input(
                "Max stocks",
                min_value=1,
                value=int(
                    current["max_stocks"]
                ),
                step=50
            )

            repeat_tolerance = st.number_input(
                "Repeat tolerance %",
                min_value=1.0,
                max_value=100.0,
                value=float(
                    current["repeat_tolerance"]
                ),
                step=1.0,
                format="%.0f"
            )

            refresh_seconds = st.number_input(
                "Refresh seconds",
                min_value=10,
                value=int(
                    current["refresh_seconds"]
                ),
                step=10
            )


        auto_scanner = st.checkbox(
            "Auto scanner",
            value=bool(
                current["auto_scanner"]
            )
        )


        if st.button(
            "Apply Settings",
            use_container_width=True
        ):

            st.session_state.settings = {
                "min_price": min_price,
                "max_price": max(
                    min_price,
                    max_price
                ),
                "min_volume": min_volume,
                "min_rvol": min_rvol,
                "min_change": min_change,
                "max_stocks": max_stocks,
                "repeat_tolerance": repeat_tolerance,
                "refresh_seconds": refresh_seconds,
                "auto_scanner": auto_scanner,
            }

            st.session_state.scan_results = None

            st.rerun()


# ============================================================
# SCANNER DISPLAY
# ============================================================

def display_scanner():

    df = st.session_state.scan_results


    st.markdown(
        '<div class="scanner-title">'
        'US Momentum Scanner'
        '</div>',
        unsafe_allow_html=True
    )


    if df is None:

        st.info(
            "Click Scan Now to start the scanner."
        )

        return


    if df.empty:

        st.warning(
            "No stocks match the current filters."
        )

        return


    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    header = st.columns(
        [
            0.70,
            1.05,
            0.70,
            0.85,
            0.65
        ]
    )

    for col, text in zip(
        header,
        [
            "Time",
            "Symbol",
            "LTP",
            "% Change",
            "Rel Vol"
        ]
    ):

        with col:

            st.markdown(
                f"**{text}**"
            )


    # --------------------------------------------------------
    # ROWS
    # --------------------------------------------------------

    for index, row in df.iterrows():

        cols = st.columns(
            [
                0.70,
                1.05,
                0.70,
                0.85,
                0.65
            ]
        )


        # ----------------------------------------------------
        # TIME
        # ----------------------------------------------------

        with cols[0]:

            st.markdown(
                f'<div class="stock-time">'
                f'{row["Time"]}'
                f'</div>',
                unsafe_allow_html=True
            )


        # ----------------------------------------------------
        # SYMBOL
        # ----------------------------------------------------

        with cols[1]:

            symbol_columns = st.columns(
                [
                    1.0,
                    0.22
                ]
            )


            with symbol_columns[0]:

                if st.button(
                    str(row["Symbol"]),
                    key=f"symbol_{index}_{row['Symbol']}",
                    use_container_width=True
                ):

                    st.session_state.selected_symbol = (
                        str(row["Symbol"])
                    )

                    st.rerun()


            with symbol_columns[1]:

                if bool(
                    row.get(
                        "Repeat",
                        False
                    )
                ):

                    st.markdown(
                        '<div class="repeat-square">'
                        '■'
                        '</div>',
                        unsafe_allow_html=True
                    )


        # ----------------------------------------------------
        # LTP
        # ----------------------------------------------------

        with cols[2]:

            st.markdown(
                f'<div class="stock-price">'
                f'{float(row["LTP"]):.2f}'
                f'</div>',
                unsafe_allow_html=True
            )


        # ----------------------------------------------------
        # CHANGE
        # ----------------------------------------------------

        with cols[3]:

            st.markdown(
                f'<div class="stock-change">'
                f'{float(row["% Change"]):.2f}%'
                f'</div>',
                unsafe_allow_html=True
            )


        # ----------------------------------------------------
        # RELATIVE VOLUME
        # ----------------------------------------------------

        with cols[4]:

            st.markdown(
                f'<div class="stock-rvol">'
                f'{float(row["Rel Vol"]):.1f}'
                f'</div>',
                unsafe_allow_html=True
            )


# ============================================================
# TOP BAR
# ============================================================

top1, top2, top3 = st.columns(
    [
        3.5,
        4.0,
        1.5
    ]
)


with top1:

    st.markdown(
        "### 📈 US Momentum Scanner"
    )


with top2:

    if st.session_state.last_scan_time:

        scan_time = (
            st.session_state
            .last_scan_time
            .strftime("%H:%M:%S")
        )

        st.caption(
            f"Last scan: {scan_time} New York time"
        )


with top3:

    show_filters()


# ============================================================
# SCAN BUTTON
# ============================================================

scan_col, blank_col = st.columns(
    [
        1.2,
        8.8
    ]
)


with scan_col:

    scan_now = st.button(
        "🔄 Scan Now",
        use_container_width=True
    )


if scan_now:

    with st.spinner(
        "Scanning US stocks..."
    ):

        run_scanner()

    st.rerun()


# ============================================================
# MAIN SCREEN
#
# IMPORTANT:
#
# Scanner = 35%
# TradingView = 65%
#
# TradingView is NOT inside the auto-refresh fragment.
# This prevents the chart from disappearing during scans.
# ============================================================

scanner_col, chart_col = st.columns(
    [
        35,
        65
    ],
    gap="small"
)


# ============================================================
# LEFT SCANNER
# ============================================================

with scanner_col:

    display_scanner()


# ============================================================
# RIGHT TRADINGVIEW
# ============================================================

with chart_col:

    selected_symbol = st.session_state.get(
        "selected_symbol"
    )


    if selected_symbol:

        show_tradingview(
            selected_symbol
        )

    else:

        st.markdown(
            """
            <div style="
                height:720px;
                display:flex;
                align-items:center;
                justify-content:center;
                background:#131722;
                color:#aaaaaa;
                font-size:18px;
            ">
                Select a stock from the scanner
                to open TradingView
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# AUTO SCANNER
#
# The scanner refreshes using Streamlit fragment.
# TradingView is deliberately outside this fragment.
# ============================================================

settings = load_settings()


if settings["auto_scanner"]:

    try:

        @st.fragment(
            run_every=int(
                settings["refresh_seconds"]
            )
        )
        def automatic_scan():

            if regular_market_hours():

                try:

                    run_scanner()

                except Exception:

                    pass


        automatic_scan()

    except Exception:

        pass
