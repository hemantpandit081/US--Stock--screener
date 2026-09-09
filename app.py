import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import os
from datetime import datetime, time
import streamlit.components.v1 as components


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="US Stock Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 0.25rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0.25rem !important;
        padding-right: 0.25rem !important;
        max-width: 100% !important;
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
        font-size: 19px;
        font-weight: 800;
        margin: 0;
        padding: 0;
    }

    .scanner-header {
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 2px;
        white-space: nowrap;
    }

    .repeat-square {
        font-size: 17px;
        font-weight: 900;
        line-height: 1;
        color: white;
        margin-left: 1px;
        margin-top: -2px;
    }

    .stock-time {
        font-size: 10px;
        white-space: nowrap;
    }

    .stock-price {
        font-size: 11px;
        white-space: nowrap;
    }

    .stock-change {
        font-size: 11px;
        white-space: nowrap;
    }

    .stock-rvol {
        font-size: 11px;
        font-weight: 700;
        white-space: nowrap;
    }

    div[data-testid="stHorizontalBlock"] {
        gap: 0.2rem;
    }

    button[kind="secondary"] {
        min-height: 28px !important;
        height: 28px !important;
        padding: 0px 8px !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# SETTINGS
# =========================================================

SETTINGS_FILE = "scanner_settings.json"

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


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)

            settings = DEFAULT_SETTINGS.copy()
            settings.update(saved)
            return settings

        except Exception:
            pass

    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass


settings = load_settings()


# =========================================================
# SESSION STATE
# =========================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "AAPL"

if "scan_now" not in st.session_state:
    st.session_state.scan_now = False


# =========================================================
# RUSSELL 2000
# =========================================================

@st.cache_data(ttl=86400)
def load_russell_2000():

    url = (
        "https://www.ishares.com/us/products/239771/"
        "ishares-russell-2000-etf/"
        "1467271812596.ajax"
        "?fileType=csv&fileName=IWM_holdings&dataType=fund"
    )

    try:
        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        text = response.text

        lines = text.splitlines()

        start = None

        for i, line in enumerate(lines):
            if "Ticker" in line and "Name" in line:
                start = i
                break

        if start is None:
            return []

        data = pd.read_csv(
            pd.io.common.StringIO(
                "\n".join(lines[start:])
            )
        )

        if "Ticker" not in data.columns:
            return []

        symbols = (
            data["Ticker"]
            .astype(str)
            .str.strip()
            .replace("-", ".", regex=False)
            .tolist()
        )

        symbols = [
            x for x in symbols
            if x
            and x.lower() != "nan"
            and x not in ["Cash", "-"]
        ]

        return symbols

    except Exception:
        return []


# =========================================================
# YFINANCE HELPERS
# =========================================================

def get_symbol_data(data, symbol):

    try:

        if isinstance(data.columns, pd.MultiIndex):

            if symbol in data.columns.get_level_values(0):

                df = data[symbol].copy()

            elif symbol in data.columns.get_level_values(1):

                df = data.xs(
                    symbol,
                    axis=1,
                    level=1
                ).copy()

            else:
                return None

        else:
            df = data.copy()

        if df.empty:
            return None

        df = df.dropna(how="all")

        return df

    except Exception:
        return None


# =========================================================
# REPEAT VOLUME
# =========================================================

def detect_repeat(session_data, tolerance=0.90):

    if session_data is None or session_data.empty:
        return False

    if "Volume" not in session_data.columns:
        return False

    volumes = (
        pd.to_numeric(
            session_data["Volume"],
            errors="coerce"
        )
        .dropna()
    )

    volumes = volumes[volumes > 0]

    if len(volumes) < 2:
        return False

    current_volume = float(volumes.iloc[-1])

    previous_volumes = volumes.iloc[:-1]

    if previous_volumes.empty:
        return False

    previous_high = float(previous_volumes.max())

    if previous_high <= 0:
        return False

    return current_volume >= previous_high * tolerance


# =========================================================
# SCAN BATCH
# =========================================================

def scan_batch(symbols):

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
        return pd.DataFrame()

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

    results = []

    for symbol in symbols:

        try:

            intraday_df = get_symbol_data(
                intraday,
                symbol
            )

            daily_df = get_symbol_data(
                daily,
                symbol
            )

            if intraday_df is None or intraday_df.empty:
                continue

            if "Close" not in intraday_df.columns:
                continue

            if "Volume" not in intraday_df.columns:
                continue

            intraday_df = intraday_df.dropna(
                subset=["Close"]
            )

            if intraday_df.empty:
                continue

            current_price = float(
                intraday_df["Close"].iloc[-1]
            )

            if not np.isfinite(current_price):
                continue

            session_volume = float(
                pd.to_numeric(
                    intraday_df["Volume"],
                    errors="coerce"
                )
                .fillna(0)
                .sum()
            )

            if session_volume < settings["min_volume"]:
                continue

            # ---------------------------------------------
            # Previous close
            # ---------------------------------------------

            previous_close = np.nan

            if (
                daily_df is not None
                and not daily_df.empty
                and "Close" in daily_df.columns
            ):

                daily_closes = (
                    pd.to_numeric(
                        daily_df["Close"],
                        errors="coerce"
                    )
                    .dropna()
                )

                if len(daily_closes) >= 2:
                    previous_close = float(
                        daily_closes.iloc[-2]
                    )

                elif len(daily_closes) == 1:
                    previous_close = float(
                        daily_closes.iloc[-1]
                    )

            if (
                pd.isna(previous_close)
                or previous_close <= 0
            ):
                continue

            percent_change = (
                (current_price - previous_close)
                / previous_close
                * 100
            )

            if percent_change < settings["min_change"]:
                continue

            # ---------------------------------------------
            # Average previous 5-day volume
            # ---------------------------------------------

            average_volume = np.nan

            if (
                daily_df is not None
                and not daily_df.empty
                and "Volume" in daily_df.columns
            ):

                daily_volumes = (
                    pd.to_numeric(
                        daily_df["Volume"],
                        errors="coerce"
                    )
                    .dropna()
                )

                if len(daily_volumes) >= 2:

                    previous_daily_volumes = (
                        daily_volumes.iloc[:-1]
                    )

                    previous_daily_volumes = (
                        previous_daily_volumes.tail(5)
                    )

                    if not previous_daily_volumes.empty:

                        average_volume = float(
                            previous_daily_volumes.mean()
                        )

            if (
                pd.isna(average_volume)
                or average_volume <= 0
            ):
                continue

            # ---------------------------------------------
            # Relative volume
            # ---------------------------------------------

            relative_volume = (
                session_volume
                / average_volume
            )

            if relative_volume < settings["min_rvol"]:
                continue

            # ---------------------------------------------
            # Repeat volume
            # ---------------------------------------------

            repeat = detect_repeat(
                intraday_df,
                settings["repeat_tolerance"] / 100
            )

            results.append(
                {
                    "Time": datetime.now().strftime("%H:%M:%S"),
                    "Symbol": symbol,
                    "LTP": current_price,
                    "Change": percent_change,
                    "Rel Vol": relative_volume,
                    "Volume": session_volume,
                    "Repeat": repeat,
                }
            )

        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)

    result_df = result_df.sort_values(
        by=["Repeat", "Rel Vol", "Change"],
        ascending=[False, False, False]
    )

    return result_df.reset_index(drop=True)


# =========================================================
# MAIN SCANNER
# =========================================================

def run_scanner():

    symbols = load_russell_2000()

    if not symbols:

        # Fallback list if IWM download fails
        symbols = [
            "AAPL",
            "AMD",
            "NVDA",
            "TSLA",
            "PLTR",
            "SOFI",
            "MARA",
            "RIOT",
            "IONQ",
            "RIVN",
            "SOUN",
            "GME",
            "AMC",
            "NIO",
            "LCID",
            "OPEN",
            "JOBY",
            "ACHR",
            "SMFL",
            "TMC",
        ]

    symbols = symbols[
        : int(settings["max_stocks"])
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

        result = scan_batch(batch)

        if not result.empty:
            all_results.append(result)

    if not all_results:
        return pd.DataFrame()

    final_df = pd.concat(
        all_results,
        ignore_index=True
    )

    final_df = final_df.sort_values(
        by=["Repeat", "Rel Vol", "Change"],
        ascending=[False, False, False]
    )

    return final_df.head(
        int(settings["max_stocks"])
    ).reset_index(drop=True)


# =========================================================
# TRADINGVIEW
# =========================================================

def show_tradingview(symbol):

    if not symbol:
        symbol = "AAPL"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                width: 100%;
                height: 100%;
                overflow: hidden;
                background: #131722;
            }}

            .tradingview-widget-container {{
                width: 100%;
                height: 100%;
            }}
        </style>
    </head>

    <body>

    <div class="tradingview-widget-container">

        <div
            class="tradingview-widget-container__widget"
            style="width:100%;height:100%;"
        ></div>

        <script
            type="text/javascript"
            src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
            async
        >
        {{
            "symbol": "NASDAQ:{symbol}",
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
            "support_host": "https://www.tradingview.com"
        }}
        </script>

    </div>

    </body>
    </html>
    """

    components.html(
        html,
        height=650,
        scrolling=False
    )


# =========================================================
# FILTERS
# =========================================================

with st.popover("⚙ Filters", use_container_width=False):

    st.markdown("### Scanner Settings")

    col1, col2 = st.columns(2)

    with col1:

        new_min_price = st.number_input(
            "Minimum price",
            min_value=0.01,
            value=float(settings["min_price"]),
            step=0.50
        )

        new_min_volume = st.number_input(
            "Minimum volume",
            min_value=0,
            value=int(settings["min_volume"]),
            step=100000
        )

        new_min_rvol = st.number_input(
            "Minimum Rel Vol",
            min_value=0.1,
            value=float(settings["min_rvol"]),
            step=0.5
        )

        new_max_stocks = st.number_input(
            "Maximum stocks",
            min_value=1,
            value=int(settings["max_stocks"]),
            step=50
        )

    with col2:

        new_max_price = st.number_input(
            "Maximum price",
            min_value=0.01,
            value=float(settings["max_price"]),
            step=1.00
        )

        new_min_change = st.number_input(
            "Minimum % change",
            min_value=-100.0,
            value=float(settings["min_change"]),
            step=1.0
        )

        new_repeat_tolerance = st.number_input(
            "Repeat tolerance %",
            min_value=1,
            max_value=100,
            value=int(settings["repeat_tolerance"]),
            step=1
        )

        new_refresh = st.number_input(
            "Refresh seconds",
            min_value=10,
            value=int(settings["refresh_seconds"]),
            step=10
        )

    new_auto = st.checkbox(
        "Auto scanner",
        value=bool(settings["auto_scanner"])
    )

    if st.button(
        "Apply Settings",
        use_container_width=True
    ):

        settings["min_price"] = new_min_price
        settings["max_price"] = new_max_price
        settings["min_volume"] = new_min_volume
        settings["min_rvol"] = new_min_rvol
        settings["min_change"] = new_min_change
        settings["max_stocks"] = new_max_stocks
        settings["repeat_tolerance"] = new_repeat_tolerance
        settings["refresh_seconds"] = new_refresh
        settings["auto_scanner"] = new_auto

        save_settings(settings)

        st.rerun()


# =========================================================
# TOP BAR
# =========================================================

top_left, top_right = st.columns(
    [8, 1]
)

with top_left:

    st.markdown(
        '<div class="main-title">US Stock Momentum Scanner</div>',
        unsafe_allow_html=True
    )

with top_right:

    if st.button(
        "🔄",
        help="Scan now"
    ):
        st.session_state.scan_now = True


# =========================================================
# MARKET TIME
# =========================================================

def regular_market_hours():

    now = datetime.now().time()

    return (
        time(9, 30)
        <= now
        <= time(16, 0)
    )


# =========================================================
# SCANNER
# =========================================================

def scanner_fragment():

    if settings["auto_scanner"]:

        if not regular_market_hours():

            st.caption(
                "US regular market is currently closed."
            )

            return

    results = run_scanner()

    # ---------------------------------------------
    # Main layout
    # ---------------------------------------------

    scanner_col, chart_col = st.columns(
        [0.65, 5.35],
        gap="small"
    )

    # =================================================
    # LEFT SCANNER
    # =================================================

    with scanner_col:

        if results.empty:

            st.markdown(
                '<div class="scanner-header">'
                'Scanned Stocks'
                '</div>',
                unsafe_allow_html=True
            )

            st.caption("No stocks matched.")

        else:

            header = st.columns(
                [0.70, 1.05, 0.70, 0.85, 0.65]
            )

            header[0].markdown(
                "Time",
                unsafe_allow_html=True
            )

            header[1].markdown(
                "Symbol",
                unsafe_allow_html=True
            )

            header[2].markdown(
                "LTP",
                unsafe_allow_html=True
            )

            header[3].markdown(
                "% Chg",
                unsafe_allow_html=True
            )

            header[4].markdown(
                "Rel Vol",
                unsafe_allow_html=True
            )

            for _, row in results.iterrows():

                row_cols = st.columns(
                    [0.70, 1.05, 0.70, 0.85, 0.65]
                )

                # -------------------------------------
                # Time
                # -------------------------------------

                row_cols[0].markdown(
                    f'<span class="stock-time">'
                    f'{row["Time"]}'
                    f'</span>',
                    unsafe_allow_html=True
                )

                # -------------------------------------
                # Symbol
                # -------------------------------------

                symbol_cols = row_cols[1].columns(
                    [1.0, 0.22]
                )

                symbol = str(
                    row["Symbol"]
                )

                if symbol_cols[0].button(
                    symbol,
                    key=f"symbol_{symbol}",
                    use_container_width=True
                ):

                    st.session_state.selected_symbol = symbol

                if bool(row["Repeat"]):

                    symbol_cols[1].markdown(
                        '<div class="repeat-square">■</div>',
                        unsafe_allow_html=True
                    )

                # -------------------------------------
                # LTP
                # -------------------------------------

                row_cols[2].markdown(
                    f'<span class="stock-price">'
                    f'{row["LTP"]:.2f}'
                    f'</span>',
                    unsafe_allow_html=True
                )

                # -------------------------------------
                # Change
                # -------------------------------------

                row_cols[3].markdown(
                    f'<span class="stock-change">'
                    f'{row["Change"]:.2f}%'
                    f'</span>',
                    unsafe_allow_html=True
                )

                # -------------------------------------
                # Relative Volume
                # -------------------------------------

                row_cols[4].markdown(
                    f'<span class="stock-rvol">'
                    f'{row["Rel Vol"]:.1f}'
                    f'</span>',
                    unsafe_allow_html=True
                )

    # =================================================
    # RIGHT TRADINGVIEW
    # =================================================

    with chart_col:

        show_tradingview(
            st.session_state.selected_symbol
        )


# =========================================================
# AUTO REFRESH
# =========================================================

if settings["auto_scanner"]:

    try:

        @st.fragment(
            run_every=int(
                settings["refresh_seconds"]
            )
        )
        def auto_scanner():

            scanner_fragment()

        auto_scanner()

    except Exception:

        scanner_fragment()

else:

    scanner_fragment()
