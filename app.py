import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime, time
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="US Stock Screener",
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
        padding-left: 0.35rem;
        padding-right: 0.35rem;
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

    .main-title {
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
        padding-top: 7px;
    }

    .stock-time {
        font-size: 11px;
        white-space: nowrap;
        padding-top: 7px;
    }

    .stock-price {
        font-size: 12px;
        font-weight: 600;
        padding-top: 7px;
    }

    .stock-change {
        font-size: 12px;
        font-weight: 600;
        padding-top: 7px;
    }

    .stock-rvol {
        font-size: 12px;
        font-weight: 700;
        padding-top: 7px;
    }

    div[data-testid="stButton"] button {
        min-height: 26px;
        height: 26px;
        padding: 0px 3px;
        font-size: 12px;
        font-weight: 700;
    }

    div[data-testid="stPopover"] button {
        min-height: 30px;
    }

    div[data-testid="stVerticalBlock"] {
        gap: 0.25rem;
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

if "scan_running" not in st.session_state:
    st.session_state.scan_running = False


# ============================================================
# SETTINGS LOADER
# ============================================================

def load_settings():

    settings = st.session_state.settings

    try:
        min_price = float(settings.get("min_price", 1.0))
    except Exception:
        min_price = 1.0

    try:
        max_price = float(settings.get("max_price", 20.0))
    except Exception:
        max_price = 20.0

    try:
        min_volume = int(settings.get("min_volume", 100000))
    except Exception:
        min_volume = 100000

    try:
        min_rvol = float(settings.get("min_rvol", 2.0))
    except Exception:
        min_rvol = 2.0

    try:
        min_change = float(settings.get("min_change", 2.0))
    except Exception:
        min_change = 2.0

    try:
        max_stocks = int(settings.get("max_stocks", 300))
    except Exception:
        max_stocks = 300

    try:
        repeat_tolerance = float(
            settings.get("repeat_tolerance", 90)
        )
    except Exception:
        repeat_tolerance = 90

    try:
        refresh_seconds = int(
            settings.get("refresh_seconds", 60)
        )
    except Exception:
        refresh_seconds = 60

    auto_scanner = bool(
        settings.get("auto_scanner", True)
    )

    min_price = max(0.01, min_price)
    max_price = max(min_price, max_price)

    min_volume = max(0, min_volume)
    min_rvol = max(0.1, min_rvol)
    min_change = max(-100.0, min_change)

    max_stocks = max(1, max_stocks)

    repeat_tolerance = min(
        100,
        max(1, repeat_tolerance)
    )

    refresh_seconds = max(
        10,
        refresh_seconds
    )

    clean_settings = {
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

    st.session_state.settings = clean_settings

    return clean_settings


settings = load_settings()


# ============================================================
# LOAD RUSSELL 2000
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

            text = response.text

            lines = text.splitlines()

            start_index = None

            for i, line in enumerate(lines):

                if "Ticker" in line and "Name" in line:
                    start_index = i
                    break

            if start_index is not None:

                csv_text = "\n".join(
                    lines[start_index:]
                )

                from io import StringIO

                df = pd.read_csv(
                    StringIO(csv_text)
                )

                possible_columns = [
                    "Ticker",
                    "Ticker Symbol",
                    "Symbol"
                ]

                ticker_column = None

                for col in possible_columns:

                    if col in df.columns:
                        ticker_column = col
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
    # FALLBACK SYMBOL LIST
    # --------------------------------------------------------

    fallback_symbols = [
        "AAL",
        "AAOI",
        "ABCL",
        "ABEO",
        "ACHR",
        "ACMR",
        "ADMA",
        "ADTX",
        "AEHR",
        "AEYE",
        "AGEN",
        "AGL",
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
        "ATER",
        "ATOS",
        "AUR",
        "AVGO",
        "BBAI",
        "BBIO",
        "BCRX",
        "BE",
        "BFLY",
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
        "CGTX",
        "CHPT",
        "CLSK",
        "CMRX",
        "COIN",
        "COMM",
        "CPSH",
        "CRDO",
        "CRK",
        "CRNC",
        "CRSP",
        "CURI",
        "CVNA",
        "CYTK",
        "DAVE",
        "DNA",
        "DNAY",
        "DNN",
        "DOCS",
        "DOMO",
        "DLO",
        "DNA",
        "EDIT",
        "ENVX",
        "EOSE",
        "EVGO",
        "EXAS",
        "FATE",
        "FCEL",
        "FFIE",
        "FGEN",
        "FIP",
        "FLNC",
        "FOLD",
        "FUBO",
        "GCT",
        "GDRX",
        "GEVO",
        "GILT",
        "GLXY",
        "GME",
        "GOEV",
        "GOSS",
        "GRAB",
        "HIMS",
        "HIVE",
        "HOOD",
        "IONQ",
        "JOBY",
        "KIND",
        "KPLUY",
        "LCID",
        "LUMN",
        "LUNR",
        "MARA",
        "MAXN",
        "MCRB",
        "MDRX",
        "MGNI",
        "MIGI",
        "MNMD",
        "MPLN",
        "MPLX",
        "MVIS",
        "NBY",
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
        "PRAX",
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
        "SABS",
        "SAVA",
        "SENS",
        "SERV",
        "SIRI",
        "SKLZ",
        "SLDP",
        "SLNO",
        "SMFL",
        "SMFL",
        "SOUN",
        "SPCE",
        "SST",
        "STNE",
        "SVMH",
        "SYRE",
        "TALK",
        "TELL",
        "TMC",
        "TMDX",
        "TNON",
        "TOST",
        "TQQQ",
        "TRIB",
        "TSLA",
        "TUP",
        "TWST",
        "U",
        "UAL",
        "UCAR",
        "UPST",
        "UPXI",
        "URG",
        "VERU",
        "VKTX",
        "VRDN",
        "WBD",
        "WKHS",
        "WOLF",
        "XBI",
        "XPEV",
        "ZIM",
        "ZOM"
    ]

    return list(
        dict.fromkeys(fallback_symbols)
    )


# ============================================================
# GET SYMBOL DATA
# ============================================================

def get_symbol_data(df, symbol):

    if df is None or df.empty:
        return None

    try:

        if isinstance(df.columns, pd.MultiIndex):

            if symbol in df.columns.get_level_values(0):

                data = df[symbol].copy()

                return data

            if symbol in df.columns.get_level_values(1):

                data = df.xs(
                    symbol,
                    axis=1,
                    level=1
                ).copy()

                return data

        return df.copy()

    except Exception:

        return None


# ============================================================
# REPEAT VOLUME DETECTION
# ============================================================

def detect_repeat(
    intraday_df,
    tolerance_percent
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

        previous_volumes = volumes.iloc[:-1]

        if previous_volumes.empty:
            return False

        previous_high = float(
            previous_volumes.max()
        )

        if previous_high <= 0:
            return False

        required_volume = (
            previous_high *
            tolerance_percent /
            100.0
        )

        return current_volume >= required_volume

    except Exception:

        return False


# ============================================================
# SCAN BATCH
# ============================================================

def scan_batch(
    symbols,
    min_price,
    max_price,
    min_volume,
    min_rvol,
    min_change,
    repeat_tolerance
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


    if intraday is None or intraday.empty:
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

            required_columns = [
                "Close",
                "Volume"
            ]

            if not all(
                col in intra_df.columns
                for col in required_columns
            ):
                continue


            # ------------------------------------------------
            # CLEAN INTRADAY DATA
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
            # CURRENT PRICE
            # ------------------------------------------------

            ltp = float(
                intra_df["Close"].iloc[-1]
            )

            if not np.isfinite(ltp):
                continue


            # ------------------------------------------------
            # PRICE FILTER
            # ------------------------------------------------

            if ltp < min_price:
                continue

            if ltp > max_price:
                continue


            # ------------------------------------------------
            # SESSION VOLUME
            # ------------------------------------------------

            volume_series = (
                intra_df["Volume"]
                .fillna(0)
            )

            session_volume = float(
                volume_series.sum()
            )

            if session_volume < min_volume:
                continue


            # ------------------------------------------------
            # PREVIOUS CLOSE
            # ------------------------------------------------

            previous_close = None

            if daily_df is not None and not daily_df.empty:

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
            # PERCENT CHANGE
            # ------------------------------------------------

            percent_change = (
                (ltp - previous_close)
                / previous_close
                * 100
            )

            if percent_change < min_change:
                continue


            # ------------------------------------------------
            # RELATIVE VOLUME
            # ------------------------------------------------

            rvol = 0.0

            if daily_df is not None and not daily_df.empty:

                if "Volume" in daily_df.columns:

                    daily_volumes = pd.to_numeric(
                        daily_df["Volume"],
                        errors="coerce"
                    ).dropna()

                    if len(daily_volumes) >= 2:

                        previous_daily_volumes = (
                            daily_volumes.iloc[:-1]
                            .tail(5)
                        )

                        if not previous_daily_volumes.empty:

                            average_daily_volume = float(
                                previous_daily_volumes.mean()
                            )

                            if average_daily_volume > 0:

                                rvol = (
                                    session_volume
                                    / average_daily_volume
                                )

            if rvol < min_rvol:
                continue


            # ------------------------------------------------
            # REPEAT VOLUME
            # ------------------------------------------------

            repeat = detect_repeat(
                intra_df,
                repeat_tolerance
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
            # RESULT
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
            settings["min_price"],
            settings["max_price"],
            settings["min_volume"],
            settings["min_rvol"],
            settings["min_change"],
            settings["repeat_tolerance"]
        )

        all_results.extend(
            batch_results
        )


    if all_results:

        result_df = pd.DataFrame(
            all_results
        )

        result_df = result_df.sort_values(
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

        result_df = result_df.reset_index(
            drop=True
        )

    else:

        result_df = pd.DataFrame(
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


    st.session_state.scan_results = result_df

    st.session_state.last_scan_time = datetime.now(
        ZoneInfo("America/New_York")
    )


# ============================================================
# TRADINGVIEW CHART
# ============================================================

def show_tradingview(symbol):

    symbol = str(symbol).upper().strip()

    chart_html = f"""
    <div class="tradingview-widget-container"
         style="height:650px;width:100%;">

      <div id="tradingview_chart"
           style="height:100%;width:100%;">
      </div>

      <script
        type="text/javascript"
        src="https://s3.tradingview.com/tv.js">
      </script>

      <script type="text/javascript">

        new TradingView.widget({{
          "autosize": true,
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
          "hide_volume": false,
          "hide_legend": false,
          "save_image": true,
          "calendar": false,
          "studies": [],
          "support_host": "https://www.tradingview.com"
        }});

      </script>

    </div>
    """

    components.html(
        chart_html,
        height=650,
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

    current_time = now.time()

    return (
        market_open
        <= current_time
        <= market_close
    )


# ============================================================
# FILTER POPOVER
# ============================================================

def show_filters():

    current = load_settings()

    with st.popover("⚙ Filters"):

        st.markdown(
            "### Scanner Filters"
        )

        col1, col2 = st.columns(2)

        with col1:

            new_min_price = st.number_input(
                "Min price",
                min_value=0.01,
                value=float(
                    current["min_price"]
                ),
                step=0.10,
                format="%.2f"
            )

            new_max_price = st.number_input(
                "Max price",
                min_value=0.01,
                value=float(
                    current["max_price"]
                ),
                step=0.50,
                format="%.2f"
            )

            new_min_volume = st.number_input(
                "Min volume",
                min_value=0,
                value=int(
                    current["min_volume"]
                ),
                step=10000
            )

            new_min_rvol = st.number_input(
                "Min Rel Vol",
                min_value=0.1,
                value=float(
                    current["min_rvol"]
                ),
                step=0.5,
                format="%.1f"
            )

        with col2:

            new_min_change = st.number_input(
                "Min % change",
                value=float(
                    current["min_change"]
                ),
                step=0.5,
                format="%.1f"
            )

            new_max_stocks = st.number_input(
                "Max stocks",
                min_value=1,
                value=int(
                    current["max_stocks"]
                ),
                step=50
            )

            new_repeat_tolerance = st.number_input(
                "Repeat tolerance %",
                min_value=1.0,
                max_value=100.0,
                value=float(
                    current["repeat_tolerance"]
                ),
                step=1.0,
                format="%.0f"
            )

            new_refresh = st.number_input(
                "Refresh seconds",
                min_value=10,
                value=int(
                    current["refresh_seconds"]
                ),
                step=10
            )


        new_auto = st.checkbox(
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
                "min_price": new_min_price,
                "max_price": max(
                    new_min_price,
                    new_max_price
                ),
                "min_volume": new_min_volume,
                "min_rvol": new_min_rvol,
                "min_change": new_min_change,
                "max_stocks": new_max_stocks,
                "repeat_tolerance": new_repeat_tolerance,
                "refresh_seconds": new_refresh,
                "auto_scanner": new_auto,
            }

            st.session_state.scan_results = None

            st.rerun()


# ============================================================
# SCANNER DISPLAY
# ============================================================

def scanner_fragment():

    # --------------------------------------------------------
    # IMPORTANT:
    # 35% scanner / 65% TradingView
    # --------------------------------------------------------

    scanner_col, chart_col = st.columns(
        [35, 65],
        gap="small"
    )


    # ========================================================
    # LEFT - SCANNER
    # ========================================================

    with scanner_col:

        st.markdown(
            '<div class="main-title">'
            'US Stock Scanner'
            '</div>',
            unsafe_allow_html=True
        )


        df = st.session_state.scan_results


        if df is None:

            st.info(
                "Click Scan Now to start the scanner."
            )

        elif df.empty:

            st.warning(
                "No stocks match the current filters."
            )

        else:

            # ------------------------------------------------
            # HEADER
            # ------------------------------------------------

            header = st.columns(
                [
                    0.70,
                    1.05,
                    0.70,
                    0.85,
                    0.65
                ]
            )

            headers = [
                "Time",
                "Symbol",
                "LTP",
                "% Change",
                "Rel Vol"
            ]

            for col, text in zip(
                header,
                headers
            ):

                with col:

                    st.markdown(
                        f"**{text}**",
                        unsafe_allow_html=True
                    )


            # ------------------------------------------------
            # STOCK ROWS
            # ------------------------------------------------

            for _, row in df.iterrows():

                cols = st.columns(
                    [
                        0.70,
                        1.05,
                        0.70,
                        0.85,
                        0.65
                    ]
                )


                # --------------------------------------------
                # TIME
                # --------------------------------------------

                with cols[0]:

                    st.markdown(
                        f'<div class="stock-time">'
                        f'{row["Time"]}'
                        f'</div>',
                        unsafe_allow_html=True
                    )


                # --------------------------------------------
                # SYMBOL + REPEAT MARKER
                # --------------------------------------------

                with cols[1]:

                    symbol_area = st.columns(
                        [
                            1.0,
                            0.22
                        ]
                    )


                    with symbol_area[0]:

                        clicked = st.button(
                            str(row["Symbol"]),
                            key=f"stock_{row['Symbol']}",
                            use_container_width=True
                        )

                        if clicked:

                            st.session_state.selected_symbol = str(
                                row["Symbol"]
                            )


                    with symbol_area[1]:

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


                # --------------------------------------------
                # LTP
                # --------------------------------------------

                with cols[2]:

                    st.markdown(
                        f'<div class="stock-price">'
                        f'{float(row["LTP"]):.2f}'
                        f'</div>',
                        unsafe_allow_html=True
                    )


                # --------------------------------------------
                # CHANGE
                # --------------------------------------------

                with cols[3]:

                    st.markdown(
                        f'<div class="stock-change">'
                        f'{float(row["% Change"]):.2f}%'
                        f'</div>',
                        unsafe_allow_html=True
                    )


                # --------------------------------------------
                # RELATIVE VOLUME
                # --------------------------------------------

                with cols[4]:

                    st.markdown(
                        f'<div class="stock-rvol">'
                        f'{float(row["Rel Vol"]):.1f}'
                        f'</div>',
                        unsafe_allow_html=True
                    )


    # ========================================================
    # RIGHT - TRADINGVIEW
    # ========================================================

    with chart_col:

        selected_symbol = st.session_state.get(
            "selected_symbol",
            None
        )


        if selected_symbol:

            show_tradingview(
                selected_symbol
            )

        else:

            st.info(
                "Select a stock to view the TradingView chart."
            )


# ============================================================
# TOP BAR
# ============================================================

top_left, top_middle, top_right = st.columns(
    [
        3.5,
        4.0,
        1.5
    ]
)


with top_left:

    st.markdown(
        "### 📈 US Stock Screener"
    )


with top_middle:

    if st.session_state.last_scan_time:

        scan_time = st.session_state.last_scan_time.strftime(
            "%H:%M:%S"
        )

        st.caption(
            f"Last scan: {scan_time} New York time"
        )


with top_right:

    show_filters()


# ============================================================
# SCAN BUTTON
# ============================================================

button_col1, button_col2 = st.columns(
    [
        1,
        8
    ]
)


with button_col1:

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
# AUTO SCANNER
# ============================================================

settings = load_settings()


if settings["auto_scanner"]:

    try:

        @st.fragment(
            run_every=int(
                settings["refresh_seconds"]
            )
        )
        def auto_scanner():

            # Only scan automatically during
            # regular US market hours.

            if regular_market_hours():

                try:

                    run_scanner()

                except Exception:
                    pass


            scanner_fragment()


        auto_scanner()

    except Exception:

        scanner_fragment()

else:

    scanner_fragment()
