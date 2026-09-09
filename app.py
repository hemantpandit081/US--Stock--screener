import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from datetime import datetime, time
from zoneinfo import ZoneInfo
from io import StringIO
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
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 0.7rem;
    padding-left: 1rem;
    padding-right: 1rem;
    max-width: 100%;
}

header[data-testid="stHeader"] {
    background: transparent;
}

div[data-testid="stVerticalBlock"] {
    gap: 0.35rem;
}

.scanner-title {
    font-size: 25px;
    font-weight: 700;
    margin-bottom: 2px;
}

.scanner-subtitle {
    font-size: 13px;
    color: #888;
    margin-bottom: 8px;
}

.stock-row {
    display: grid;
    grid-template-columns:
        65px
        90px
        85px
        85px
        70px;
    align-items: center;
    min-height: 34px;
    border-bottom: 1px solid rgba(128,128,128,0.18);
    font-size: 13px;
}

.stock-header {
    font-weight: 700;
    color: #999;
    border-bottom: 1px solid rgba(128,128,128,0.35);
}

.ticker-link {
    text-decoration: none;
    font-weight: 700;
}

.repeat-dot {
    color: white;
    font-size: 13px;
    margin-left: 4px;
}

.positive {
    color: #16a34a;
    font-weight: 600;
}

.negative {
    color: #dc2626;
    font-weight: 600;
}

.tv-container {
    width: 100%;
}

.small-text {
    font-size: 12px;
    color: #888;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# SESSION STATE
# ============================================================

defaults = {
    "min_price": 1.0,
    "max_price": 20.0,
    "min_volume": 100000,
    "min_rvol": 2.0,
    "min_change": 2.0,
    "max_stocks": 300,
    "repeat_tolerance": 90,
    "refresh_seconds": 60,
    "auto_scanner": False,

    "scan_results": None,
    "selected_symbol": "AAPL",
    "last_scan": None,
    "scan_running": False,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# SETTINGS
# ============================================================

settings = {
    "min_price": st.session_state.min_price,
    "max_price": st.session_state.max_price,
    "min_volume": st.session_state.min_volume,
    "min_rvol": st.session_state.min_rvol,
    "min_change": st.session_state.min_change,
    "max_stocks": st.session_state.max_stocks,
    "repeat_tolerance": st.session_state.repeat_tolerance,
    "refresh_seconds": st.session_state.refresh_seconds,
    "auto_scanner": st.session_state.auto_scanner,
}


# ============================================================
# RUSSELL 2000 UNIVERSE
# ============================================================

@st.cache_data(ttl=86400)
def load_russell_2000():

    url = (
        "https://www.ishares.com/us/products/"
        "239710/ishares-russell-2000-etf/"
        "1467271812596.ajax?"
        "fileType=csv&fileName=IWM_holdings&dataType=fund"
    )

    try:

        response = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent":
                "Mozilla/5.0"
            }
        )

        text = response.text

        df = pd.read_csv(
            StringIO(text),
            skiprows=9
        )

        if "Ticker" in df.columns:

            symbols = (
                df["Ticker"]
                .dropna()
                .astype(str)
                .str.strip()
                .tolist()
            )

            symbols = [
                s for s in symbols
                if s.isalpha()
                and 1 <= len(s) <= 5
            ]

            if len(symbols) > 100:
                return symbols

    except Exception:
        pass


    # Fallback universe
    fallback = [
        "AAOI", "AARD", "ABCL", "ABEO", "ABOS",
        "ABSI", "ABVC", "ACAD", "ACCD", "ACDC",
        "ACMR", "ACON", "ACRS", "ACTG", "ADMA",
        "ADSE", "AEHR", "AEYE", "AFBI", "AGEN",
        "AGFY", "AGIO", "AGL", "AHCO", "AIFF",
        "AKBA", "ALDX", "ALLK", "ALLO", "ALOT",
        "AMTX", "ANAB", "ANIK", "ANIX", "APLT",
        "APOG", "APPF", "APPS", "ARAY", "ARCT",
        "ARDX", "AREC", "ARGX", "ARQT", "ARRY",
        "ASLE", "ASND", "ASPI", "ASTE", "ASTS",
        "ATEX", "ATLC", "ATOM", "ATOS", "ATRA",
        "ATRC", "AUB", "AUDC", "AUPH", "AVAH",
        "AVDX", "AVPT", "AXGN", "AXSM", "AZTA",
        "BAND", "BBIO", "BCAB", "BCEL", "BCLI",
        "BDTX", "BEAM", "BEAT", "BFLY", "BGFV",
        "BIRD", "BKSY", "BLDE", "BLFS", "BLMN",
        "BLUE", "BMEA", "BMRN", "BNGO", "BOWL",
        "BRDS", "BRLT", "BSVN", "BTDR", "BTRS",
        "CABA", "CARG", "CASS", "CATY", "CBAY",
        "CCOI", "CDMO", "CDNA", "CELC", "CERT",
        "CERS", "CFLT", "CGEM", "CHPT", "CISO",
        "CLDX", "CLNE", "CLSK", "CMPO", "CNDT",
        "COGT", "COMM", "COOK", "CORT", "CRDO",
        "CRGY", "CRNC", "CRNX", "CRSP", "CRVS",
        "CSIQ", "CTKB", "CTLP", "CTMX", "CTOS",
        "CURI", "CVAC", "CVCO", "CYTK", "DAWN",
        "DCFC", "DCTH", "DFLI", "DICE", "DLO",
        "DNLI", "DOCN", "DOMO", "DRS", "DSGN",
        "DUOL", "DVAX", "DXCM", "EAF", "EDIT",
        "EGRX", "ELVN", "EMBC", "ENPH", "ENVX",
        "EOLS", "EQRX", "ERAS", "EVGO", "EVLV",
        "EVRI", "EXAI", "EXPI", "FATE", "FBIO",
        "FCEL", "FGEN", "FLGT", "FOLD", "FORM",
        "FREQ", "FROG", "FUBO", "FULC", "GCT",
        "GDRX", "GERN", "GILT", "GLBE", "GLDD",
        "GMAB", "GNCA", "GOSS", "GRAB", "GRCL",
        "GROY", "HARP", "HAYW", "HCAT", "HCSG",
        "HIMS", "HLVX", "HRTX", "HUMA", "HYPR",
        "ICVX", "IDYA", "IMAB", "IMCR", "IMMP",
        "IMNM", "IMUX", "INDI", "INOD", "INVA",
        "IONQ", "IRDM", "IRON", "ITOS", "IVVD",
        "JAMF", "KALA", "KROS", "KURA", "KYMR",
        "LCTX", "LESL", "LFST", "LITE", "LMND",
        "LNW", "LOCO", "LQDA", "LSPD", "LUMN",
        "LUNA", "MARA", "MAXN", "MBLY", "MCRI",
        "MDGL", "MDRX", "MGNX", "MIRM", "MLAB",
        "MNKD", "MNTV", "MODV", "MPLN", "MRVI",
        "MRSN", "MRTX", "MSTR", "MTTR", "MVST",
        "MYGN", "NAMS", "NEO", "NERV", "NKTR",
        "NLTX", "NMRA", "NNOX", "NOVT", "NRIX",
        "NTLA", "NUVB", "NVAX", "NVCR", "NVTS",
        "OCGN", "OCUL", "ODD", "OFIX", "OLMA",
        "OMCL", "ONON", "OPK", "ORIC", "ORRY",
        "OTLK", "OUST", "OVID", "OXM", "PACB",
        "PAGS", "PAR", "PCT", "PETS", "PGNY",
        "PHAT", "PHR", "PLCE", "PLUG", "PLUR",
        "POET", "PRAX", "PRCT", "PRLD", "PRTA",
        "PSTX", "PTGX", "PUBM", "PYXS", "QDEL",
        "QFIN", "QIPT", "QLYS", "QRTEA", "QUBT",
        "RANI", "RAPT", "RBBN", "RCAT", "RDNT",
        "REAL", "REKR", "RELY", "REPL", "RETA",
        "RGTI", "RILY", "RKLB", "RLAY", "RMTI",
        "RNA", "RNAC", "ROIV", "ROOT", "RUM",
        "RXRX", "RYTM", "SAGE", "SAVA", "SBCF",
        "SDGR", "SEAT", "SEEL", "SGMO", "SHCR",
        "SILK", "SINT", "SKIN", "SLDB", "SLDP",
        "SLNO", "SMFL", "SNDL", "SOFI", "SONO",
        "SPCE", "SPT", "SRRK", "STEM", "STER",
        "STGW", "STNE", "SVC", "SWIM", "SYRE",
        "TALK", "TARS", "TBIO", "TCMD", "TELL",
        "TGTX", "TMC", "TMDX", "TNDM", "TNYA",
        "TOI", "TRDA", "TRUP", "TTOO", "TUP",
        "TWST", "TXG", "UAVS", "UBER", "UNCY",
        "UPST", "UPWK", "URGN", "USLM", "VBNK",
        "VCEL", "VIR", "VKTX", "VLD", "VRDN",
        "VRNA", "VRNS", "VSTM", "VTYX", "WALD",
        "WAVE", "WBD", "WFRD", "WKHS", "WOOF",
        "WRBY", "XENE", "XMTR", "XOMA", "YOU",
        "ZIM", "ZETA", "ZEV", "ZURA"
    ]

    return fallback


# ============================================================
# GET SYMBOL DATA
# ============================================================

@st.cache_data(ttl=45)
def get_symbol_data(symbol):

    try:

        ticker = yf.Ticker(symbol)

        intraday = ticker.history(
            period="1d",
            interval="1m",
            prepost=False,
            auto_adjust=False
        )

        if intraday is None or intraday.empty:
            return None

        intraday = intraday.dropna(
            subset=["Close", "Volume"]
        )

        if intraday.empty:
            return None

        current_price = float(
            intraday["Close"].iloc[-1]
        )

        current_volume = float(
            intraday["Volume"].iloc[-1]
        )

        day_volume = float(
            intraday["Volume"].sum()
        )

        first_price = float(
            intraday["Close"].iloc[0]
        )

        if first_price <= 0:
            return None

        percent_change = (
            (current_price - first_price)
            / first_price
            * 100
        )

        # Previous 5 daily average volume
        daily = ticker.history(
            period="10d",
            interval="1d",
            auto_adjust=False
        )

        avg_daily_volume = np.nan

        if daily is not None and not daily.empty:

            daily_volumes = (
                daily["Volume"]
                .dropna()
                .tail(5)
            )

            if len(daily_volumes) > 0:
                avg_daily_volume = (
                    daily_volumes.mean()
                )

        if (
            pd.isna(avg_daily_volume)
            or avg_daily_volume <= 0
        ):
            rvol = 0
        else:
            rvol = (
                day_volume
                / avg_daily_volume
            )

        # Highest completed/current 1-minute volume
        previous_highest = (
            intraday["Volume"]
            .iloc[:-1]
            .max()
            if len(intraday) > 1
            else 0
        )

        if pd.isna(previous_highest):
            previous_highest = 0

        return {
            "symbol": symbol,
            "price": current_price,
            "volume": current_volume,
            "day_volume": day_volume,
            "change": percent_change,
            "rvol": rvol,
            "previous_highest": previous_highest,
        }

    except Exception:
        return None


# ============================================================
# REPEAT DETECTION
# ============================================================

def detect_repeat(
    current_volume,
    previous_highest,
    tolerance
):

    if previous_highest <= 0:
        return False

    required_volume = (
        previous_highest
        * tolerance
        / 100
    )

    return current_volume >= required_volume


# ============================================================
# SCAN BATCH
# ============================================================

def scan_batch(symbols):

    results = []

    for symbol in symbols:

        data = get_symbol_data(symbol)

        if data is None:
            continue

        price = data["price"]
        volume = data["volume"]
        rvol = data["rvol"]
        change = data["change"]

        # Price filter
        if price < settings["min_price"]:
            continue

        if price > settings["max_price"]:
            continue

        # Volume filter
        if volume < settings["min_volume"]:
            continue

        # Relative volume
        if rvol < settings["min_rvol"]:
            continue

        # Percentage change
        if change < settings["min_change"]:
            continue

        repeat = detect_repeat(
            data["volume"],
            data["previous_highest"],
            settings["repeat_tolerance"]
        )

        data["repeat"] = repeat

        results.append(data)

    return results


# ============================================================
# RUN SCANNER
# ============================================================

def run_scanner():

    if st.session_state.scan_running:
        return

    st.session_state.scan_running = True

    try:

        symbols = load_russell_2000()

        all_results = []

        # Scan in manageable batches
        batch_size = 25

        progress = st.progress(0)

        total = len(symbols)

        for start in range(
            0,
            total,
            batch_size
        ):

            batch = symbols[
                start:start + batch_size
            ]

            batch_results = scan_batch(batch)

            all_results.extend(
                batch_results
            )

            progress.progress(
                min(
                    (start + batch_size) / total,
                    1.0
                )
            )

        progress.empty()

        if all_results:

            df = pd.DataFrame(
                all_results
            )

            # Sort:
            # repeat stocks first,
            # then RVOL
            df = df.sort_values(
                by=["repeat", "rvol", "change"],
                ascending=[False, False, False]
            )

            df = df.head(
                int(settings["max_stocks"])
            )

            st.session_state.scan_results = df

            if (
                st.session_state.selected_symbol
                not in df["symbol"].tolist()
            ):
                st.session_state.selected_symbol = (
                    df.iloc[0]["symbol"]
                )

        else:

            st.session_state.scan_results = (
                pd.DataFrame()
            )

        st.session_state.last_scan = (
            datetime.now(
                ZoneInfo("America/New_York")
            )
        )

    finally:

        st.session_state.scan_running = False


# ============================================================
# MARKET HOURS
# ============================================================

def regular_market_hours():

    now = datetime.now(
        ZoneInfo("America/New_York")
    )

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
# TRADINGVIEW
# ============================================================

def tradingview_chart(symbol):

    symbol = symbol.upper()

    html = f"""
    <div style="
        width:100%;
        height:760px;
        background:#000;
    ">

    <div id="tradingview_chart"
         style="width:100%;height:100%;">
    </div>

    <script src="https://s3.tradingview.com/tv.js"></script>

    <script>

    new TradingView.widget({{

        "autosize": true,

        "symbol": "NASDAQ:{symbol}",

        "interval": "1",

        "timezone": "America/New_York",

        "theme": "dark",

        "style": "1",

        "locale": "en",

        "toolbar_bg": "#000000",

        "enable_publishing": false,

        "hide_top_toolbar": false,

        "hide_side_toolbar": false,

        "allow_symbol_change": true,

        "save_image": true,

        "container_id": "tradingview_chart"

    }});

    </script>

    </div>
    """

    components.html(
        html,
        height=760
    )


# ============================================================
# FILTER UI
# ============================================================

def filter_panel():

    with st.popover("⚙ Filters"):

        st.subheader("Scanner Filters")

        st.session_state.min_price = st.number_input(
            "Min Price",
            min_value=0.01,
            value=float(st.session_state.min_price),
            step=0.50
        )

        st.session_state.max_price = st.number_input(
            "Max Price",
            min_value=0.01,
            value=float(st.session_state.max_price),
            step=1.00
        )

        st.session_state.min_volume = st.number_input(
            "Min Volume",
            min_value=0,
            value=int(st.session_state.min_volume),
            step=100000
        )

        st.session_state.min_rvol = st.number_input(
            "Min Relative Volume",
            min_value=0.1,
            value=float(st.session_state.min_rvol),
            step=0.5
        )

        st.session_state.min_change = st.number_input(
            "Min % Change",
            min_value=0.0,
            value=float(st.session_state.min_change),
            step=0.5
        )

        st.session_state.max_stocks = st.number_input(
            "Max Displayed Stocks",
            min_value=10,
            max_value=500,
            value=int(st.session_state.max_stocks),
            step=10
        )

        st.session_state.repeat_tolerance = st.slider(
            "Repeat Volume Tolerance %",
            min_value=50,
            max_value=100,
            value=int(
                st.session_state.repeat_tolerance
            ),
            step=5
        )

        st.session_state.refresh_seconds = st.number_input(
            "Refresh Seconds",
            min_value=30,
            max_value=600,
            value=int(
                st.session_state.refresh_seconds
            ),
            step=30
        )

        st.session_state.auto_scanner = st.checkbox(
            "Auto Scanner",
            value=bool(
                st.session_state.auto_scanner
            )
        )


# ============================================================
# DISPLAY SCANNER
# ============================================================

def display_scanner():

    st.markdown(
        '<div class="scanner-title">'
        'US Momentum Scanner'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="scanner-subtitle">'
        '1-minute momentum • Relative volume • Repeat volume'
        '</div>',
        unsafe_allow_html=True
    )

    results = st.session_state.scan_results

    # Header
    st.markdown(
        """
        <div class="stock-row stock-header">
            <div>Time</div>
            <div>Symbol</div>
            <div>LTP</div>
            <div>% Change</div>
            <div>Rel Vol</div>
        </div>
        """,
        unsafe_allow_html=True
    )

    if results is None:

        st.info(
            "Click **Scan Now** to start the scanner."
        )

        return

    if results.empty:

        st.warning(
            "No stocks match the current filters."
        )

        return

    for _, row in results.iterrows():

        symbol = row["symbol"]

        price = float(row["price"])

        change = float(row["change"])

        rvol = float(row["rvol"])

        repeat = bool(row["repeat"])

        current_time = datetime.now(
            ZoneInfo("America/New_York")
        ).strftime("%H:%M")

        change_class = (
            "positive"
            if change >= 0
            else "negative"
        )

        dot = (
            '<span class="repeat-dot">●</span>'
            if repeat
            else ""
        )

        # Use Streamlit button for clickable ticker
        cols = st.columns(
            [0.75, 1.05, 0.9, 0.95, 0.7]
        )

        with cols[0]:
            st.markdown(
                f'<span class="small-text">'
                f'{current_time}'
                f'</span>',
                unsafe_allow_html=True
            )

        with cols[1]:

            if st.button(
                f"{symbol}  {'●' if repeat else ''}",
                key=f"stock_{symbol}",
                use_container_width=False
            ):

                st.session_state.selected_symbol = symbol

                st.rerun()

        with cols[2]:

            st.markdown(
                f"${price:.2f}",
                unsafe_allow_html=True
            )

        with cols[3]:

            st.markdown(
                f'<span class="{change_class}">'
                f'{change:+.2f}%'
                f'</span>',
                unsafe_allow_html=True
            )

        with cols[4]:

            st.markdown(
                f"{rvol:.1f}",
                unsafe_allow_html=True
            )


# ============================================================
# TOP BAR
# ============================================================

top1, top2, top3, top4 = st.columns(
    [3, 1, 1, 1]
)

with top1:

    if st.session_state.last_scan:

        last_scan = (
            st.session_state.last_scan
            .strftime("%H:%M:%S ET")
        )

        st.caption(
            f"Last scan: {last_scan}"
        )

    else:

        st.caption(
            "Scanner ready"
        )


with top2:

    filter_panel()


with top3:

    if st.button(
        "🔎 Scan Now",
        use_container_width=True
    ):

        run_scanner()

        st.rerun()


with top4:

    if st.session_state.scan_running:

        st.caption(
            "Scanning..."
        )

    elif st.session_state.auto_scanner:

        st.caption(
            "Auto Scanner: ON"
        )

    else:

        st.caption(
            "Auto Scanner: OFF"
        )


# ============================================================
# MAIN LAYOUT
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT — SCANNER
# ============================================================

with left:

    display_scanner()


# ============================================================
# RIGHT — TRADINGVIEW
# ============================================================

with right:

    selected = (
        st.session_state.selected_symbol
    )

    st.markdown(
        f"### {selected}"
    )

    tradingview_chart(
        selected
    )


# ============================================================
# AUTO SCANNER
# ============================================================

# IMPORTANT:
# Auto scanner only starts AFTER the user has
# performed the first scan.
#
# This prevents the initial page from becoming
# completely white while yfinance scans hundreds
# of stocks.

if (
    st.session_state.auto_scanner
    and st.session_state.scan_results is not None
):

    @st.fragment(
        run_every=int(
            st.session_state.refresh_seconds
        )
    )
    def automatic_scan():

        if regular_market_hours():

            run_scanner()

            st.rerun()


    automatic_scan()
