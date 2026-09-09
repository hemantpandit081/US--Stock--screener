import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

st.set_page_config(
    page_title="US Stock Screener",
    layout="wide"
)

st.title("🇺🇸 US Stock Momentum Screener")

# -----------------------------
# SIDEBAR FILTERS
# -----------------------------

st.sidebar.header("Scanner Filters")

min_price = st.sidebar.number_input(
    "Minimum Price ($)",
    min_value=0.0,
    value=1.0,
    step=0.10
)

max_price = st.sidebar.number_input(
    "Maximum Price ($)",
    min_value=0.0,
    value=20.0,
    step=0.10
)

min_volume = st.sidebar.number_input(
    "Minimum Volume",
    min_value=0,
    value=100000,
    step=10000
)

min_rvol = st.sidebar.number_input(
    "Minimum Relative Volume (x)",
    min_value=0.0,
    value=10.0,
    step=0.5
)

min_change = st.sidebar.number_input(
    "Minimum % Change",
    value=5.0,
    step=0.5
)

refresh = st.sidebar.button("🔄 Scan Market")

# -----------------------------
# STOCK LIST
# -----------------------------

stocks = [
    "AAPL", "MSFT", "NVDA", "AMD", "TSLA",
    "AMZN", "META", "GOOGL", "NFLX", "PLTR",
    "SOFI", "NIO", "MARA", "RIOT", "COIN",
    "RIVN", "LCID", "SMCI", "GME", "AMC"
]

# -----------------------------
# GET MARKET DATA
# -----------------------------

@st.cache_data(ttl=60)
def get_stock_data():

    results = []

    for ticker in stocks:

        try:
            data = yf.download(
                ticker,
                period="5d",
                interval="1d",
                progress=False,
                auto_adjust=False
            )

            if data.empty:
                continue

            close = float(data["Close"].iloc[-1])
            volume = int(data["Volume"].iloc[-1])

            if len(data) >= 2:
                previous_close = float(data["Close"].iloc[-2])
                change = ((close - previous_close) / previous_close) * 100
            else:
                change = 0

            # Temporary RVOL calculation
            if len(data) >= 5:
                average_volume = data["Volume"].iloc[:-1].mean()
                rvol = volume / average_volume if average_volume > 0 else 0
            else:
                rvol = 0

            results.append({
                "Ticker": ticker,
                "Price": close,
                "Change %": change,
                "Volume": volume,
                "RVOL": rvol
            })

        except Exception:
            continue

    return pd.DataFrame(results)


# -----------------------------
# RUN SCANNER
# -----------------------------

if refresh or "data" not in st.session_state:

    with st.spinner("Scanning US stocks..."):
        st.session_state.data = get_stock_data()


df = st.session_state.data


# -----------------------------
# APPLY FILTERS
# -----------------------------

if not df.empty:

    filtered = df[
        (df["Price"] >= min_price) &
        (df["Price"] <= max_price) &
        (df["Volume"] >= min_volume) &
        (df["RVOL"] >= min_rvol) &
        (df["Change %"] >= min_change)
    ]

    filtered = filtered.sort_values(
        "RVOL",
        ascending=False
    )

    # Format display
    display_df = filtered.copy()

    display_df["Price"] = display_df["Price"].map(
        lambda x: f"${x:.2f}"
    )

    display_df["Change %"] = display_df["Change %"].map(
        lambda x: f"{x:.2f}%"
    )

    display_df["Volume"] = display_df["Volume"].map(
        lambda x: f"{x:,}"
    )

    display_df["RVOL"] = display_df["RVOL"].map(
        lambda x: f"{x:.2f}x"
    )

    st.subheader(
        f"Stocks Found: {len(filtered)}"
    )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

else:

    st.warning(
        "No stocks matched your current filters."
    )


# -----------------------------
# LAST UPDATE
# -----------------------------

st.caption(
    "Last scan: "
    + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)






