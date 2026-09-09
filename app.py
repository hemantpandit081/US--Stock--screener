import streamlit as st
import pandas as pd
import yfinance as yf
import streamlit.components.v1 as components
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="US Stock Momentum Scanner",
    layout="wide"
)

st.title("🇺🇸 US Stock Momentum Scanner")


# ============================================================
# MARKET STATUS
# ============================================================

def get_market_status():

    now = datetime.now(ZoneInfo("America/New_York"))
    current_time = now.time()

    premarket_start = datetime.strptime("04:00", "%H:%M").time()
    market_start = datetime.strptime("09:30", "%H:%M").time()
    market_end = datetime.strptime("16:00", "%H:%M").time()
    after_hours_end = datetime.strptime("20:00", "%H:%M").time()

    if premarket_start <= current_time < market_start:
        return "🟡 PRE-MARKET"

    elif market_start <= current_time < market_end:
        return "🟢 MARKET OPEN"

    elif market_end <= current_time < after_hours_end:
        return "🔵 AFTER-HOURS"

    return "🔴 MARKET CLOSED"


st.write("Market status:", get_market_status())


# ============================================================
# SIDEBAR FILTERS
# ============================================================

st.sidebar.header("Scanner Filters")

min_price = st.sidebar.number_input(
    "Minimum Price",
    min_value=0.01,
    value=1.00,
    step=0.50
)

max_price = st.sidebar.number_input(
    "Maximum Price",
    min_value=0.01,
    value=20.00,
    step=1.00
)

min_volume = st.sidebar.number_input(
    "Minimum Volume",
    min_value=0,
    value=100000,
    step=50000
)

min_rvol = st.sidebar.number_input(
    "Minimum RVOL",
    min_value=0.0,
    value=2.0,
    step=0.5
)

min_change = st.sidebar.number_input(
    "Minimum Change %",
    min_value=-100.0,
    value=2.0,
    step=1.0
)

scan_button = st.sidebar.button(
    "🔍 Scan Now",
    use_container_width=True
)


# ============================================================
# STOCK LIST
# ============================================================

@st.cache_data(ttl=300)
def get_stock_universe():

    return [
        "AAPL",
        "NVDA",
        "TSLA",
        "AMD",
        "AMZN",
        "META",
        "MSFT",
        "GOOGL",
        "NFLX",
        "PLTR",
        "MSTR",
        "COIN",
        "SMCI",
        "SOFI",
        "NIO",
        "RIVN",
        "LCID",
        "MARA",
        "RIOT",
        "IONQ",
        "BBAI",
        "SOUN",
        "AI",
        "HOOD",
        "RKLB",
        "GME",
        "AMC",
        "BB",
        "OPEN",
        "FFIE"
    ]


# ============================================================
# STOCK CALCULATION
# ============================================================

def calculate_stock(ticker):

    try:

        stock = yf.Ticker(ticker)

        data = stock.history(
            period="5d",
            interval="5m",
            prepost=False
        )

        if data.empty:
            return None

        data = data.dropna()

        if len(data) < 20:
            return None

        # Latest price
        latest = data.iloc[-1]

        price = float(latest["Close"])

        # ----------------------------------------------------
        # PREVIOUS DAY CLOSE
        # ----------------------------------------------------

        daily = stock.history(
            period="5d",
            interval="1d"
        )

        if daily.empty or len(daily) < 2:
            return None

        daily = daily.dropna()

        previous_close = float(
            daily["Close"].iloc[-2]
        )

        if previous_close <= 0:
            return None

        change_percent = (
            (price - previous_close)
            / previous_close
            * 100
        )

        # ----------------------------------------------------
        # CURRENT SESSION VOLUME
        # ----------------------------------------------------

        latest_date = data.index[-1].date()

        session_data = data[
            data.index.date == latest_date
        ]

        session_volume = float(
            session_data["Volume"].sum()
        )

        # ----------------------------------------------------
        # RELATIVE VOLUME
        # ----------------------------------------------------

        data["DateOnly"] = data.index.date

        daily_volume = (
            data
            .groupby("DateOnly")["Volume"]
            .sum()
        )

        if len(daily_volume) >= 2:

            previous_volumes = daily_volume.iloc[:-1]

            average_volume = (
                previous_volumes.mean()
            )

            if average_volume > 0:

                rvol = (
                    session_volume
                    / average_volume
                )

            else:

                rvol = 0

        else:

            rvol = 0

        return {

            "Time": data.index[-1].strftime("%H:%M"),

            "Symbol": ticker,

            "LTP": round(price, 2),

            "% Change": round(
                change_percent,
                2
            ),

            "Rel Vol": round(
                rvol,
                2
            ),

            "Volume": int(
                session_volume
            )
        }

    except Exception:

        return None


# ============================================================
# RUN SCANNER
# ============================================================

def run_scanner():

    stocks = get_stock_universe()

    results = []

    progress = st.progress(0)

    total = len(stocks)

    for i, ticker in enumerate(stocks):

        result = calculate_stock(ticker)

        if result is not None:

            results.append(result)

        progress.progress(
            (i + 1) / total
        )

    progress.empty()

    if results:

        return pd.DataFrame(results)

    return pd.DataFrame(
        columns=[
            "Time",
            "Symbol",
            "LTP",
            "% Change",
            "Rel Vol",
            "Volume"
        ]
    )


# ============================================================
# SESSION STATE
# ============================================================

if "scanner_data" not in st.session_state:

    st.session_state.scanner_data = pd.DataFrame()


if "selected_ticker" not in st.session_state:

    st.session_state.selected_ticker = None


# ============================================================
# FIRST SCAN
# ============================================================

if (
    scan_button
    or st.session_state.scanner_data.empty
):

    st.session_state.scanner_data = run_scanner()


df = st.session_state.scanner_data.copy()


# ============================================================
# FILTER STOCKS
# ============================================================

filtered = df.copy()

if not filtered.empty:

    filtered = filtered[
        (filtered["LTP"] >= min_price)
        &
        (filtered["LTP"] <= max_price)
        &
        (filtered["Volume"] >= min_volume)
        &
        (filtered["Rel Vol"] >= min_rvol)
        &
        (filtered["% Change"] >= min_change)
    ]

    filtered = filtered.sort_values(
        "Rel Vol",
        ascending=False
    )


# ============================================================
# LEFT AND RIGHT
# ============================================================

scanner_col, chart_col = st.columns(
    [45, 55],
    gap="medium"
)


# ============================================================
# LEFT SIDE — SCANNER
# ============================================================

with scanner_col:

    st.subheader("📊 Stock Scanner")

    if filtered.empty:

        st.warning(
            "No stocks match your filters."
        )

        st.info(
            "Try lowering RVOL or Change %."
        )

    else:

        display_df = filtered[
            [
                "Time",
                "Symbol",
                "LTP",
                "% Change",
                "Rel Vol"
            ]
        ].copy()

        # CLICKABLE TABLE
        event = st.dataframe(

            display_df,

            use_container_width=True,

            hide_index=True,

            height=700,

            selection_mode="single-row",

            on_select="rerun",

            key="scanner_table",

            column_config={

                "Time": st.column_config.TextColumn(
                    "Time"
                ),

                "Symbol": st.column_config.TextColumn(
                    "Symbol"
                ),

                "LTP": st.column_config.NumberColumn(
                    "LTP",
                    format="%.2f"
                ),

                "% Change": st.column_config.NumberColumn(
                    "% Change",
                    format="%.2f"
                ),

                "Rel Vol": st.column_config.NumberColumn(
                    "Rel Vol",
                    format="%.2f"
                )
            }
        )

        # CHECK WHICH ROW WAS CLICKED

        if event.selection.rows:

            row_number = event.selection.rows[0]

            clicked_stock = display_df.iloc[
                row_number
            ]["Symbol"]

            st.session_state.selected_ticker = (
                clicked_stock
            )


# ============================================================
# DEFAULT STOCK
# ============================================================

if (
    st.session_state.selected_ticker is None
    and not filtered.empty
):

    st.session_state.selected_ticker = (
        filtered.iloc[0]["Symbol"]
    )


# ============================================================
# RIGHT SIDE — TRADINGVIEW
# ============================================================

with chart_col:

    st.subheader("📈 TradingView Chart")

    selected_ticker = (
        st.session_state.selected_ticker
    )

    if selected_ticker:

        st.caption(
            f"Selected: {selected_ticker}"
        )

        tradingview_html = f"""
        <!DOCTYPE html>

        <html>

        <head>

            <meta charset="UTF-8">

            <script
                type="text/javascript"
                src="https://s3.tradingview.com/tv.js">
            </script>

            <style>

                html,
                body {{

                    margin: 0;
                    padding: 0;

                    width: 100%;
                    height: 100%;

                    overflow: hidden;
                }}

                #tradingview_chart {{

                    width: 100%;
                    height: 700px;
                }}

            </style>

        </head>

        <body>

            <div id="tradingview_chart">
            </div>

            <script>

                new TradingView.widget({{

                    "container_id":
                        "tradingview_chart",

                    "autosize": true,

                    "symbol":
                        "NASDAQ:{selected_ticker}",

                    "interval": "5",

                    "timezone":
                        "America/New_York",

                    "theme": "dark",

                    "style": "1",

                    "locale": "en",

                    "enable_publishing": false,

                    "allow_symbol_change": true,

                    "hide_top_toolbar": false,

                    "hide_legend": false,

                    "save_image": false,

                    "withdateranges": true,

                    "studies": []

                }});

            </script>

        </body>

        </html>
        """

        components.html(
            tradingview_html,
            height=710,
            scrolling=False
        )

    else:

        st.info(
            "Click a stock in the scanner."
        )


# ============================================================
# REFRESH BUTTON
# ============================================================

st.sidebar.markdown("---")

if st.sidebar.button(
    "🔄 Refresh Scanner",
    use_container_width=True
):

    st.session_state.scanner_data = run_scanner()

    st.rerun()
