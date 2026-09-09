import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="US Stock Screener",
    layout="wide"
)

st.title("🇺🇸 US Stock Momentum Screener")

# Sidebar filters
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

st.subheader("Scanner")

# Temporary sample data
data = {
    "Ticker": ["ABC", "XYZ", "TEST", "MOMO"],
    "Price": [4.20, 7.80, 12.50, 2.95],
    "Change %": [15.2, 11.5, 7.3, 28.4],
    "Volume": [2400000, 1800000, 650000, 950000],
    "RVOL": [18.4, 12.7, 8.2, 25.6]
}

df = pd.DataFrame(data)

# Apply filters
filtered = df[
    (df["Price"] >= min_price) &
    (df["Price"] <= max_price) &
    (df["Volume"] >= min_volume) &
    (df["RVOL"] >= min_rvol) &
    (df["Change %"] >= min_change)
]

# Sort by RVOL
filtered = filtered.sort_values(
    "RVOL",
    ascending=False
)

st.dataframe(
    filtered,
    use_container_width=True,
    hide_index=True
)
