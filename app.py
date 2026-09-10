import streamlit as st
import yfinance as yf
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="US Stock Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# SETTINGS
# =========================================================

AUTO_REFRESH_SECONDS = 60


# =========================================================
# PAGE STYLE
# =========================================================

st.markdown(
    """
    <style>

    /* Reduce empty space */
    .block-container {
        padding-top: 0.5rem;
        padding-bottom: 0.2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    /* Hide Streamlit footer */
    footer {
        visibility: hidden;
    }

    /* Stock buttons */
    div.stButton > button {
        width: 100%;
        min-height: 34px;
        padding: 3px 6px;
        font-size: 13px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# AUTO REFRESH
# =========================================================

st.markdown(
    f"""
    <meta http-equiv="refresh"
    content="{AUTO_REFRESH_SECONDS}">
    """,
    unsafe_allow_html=True
)


# =========================================================
# SESSION STATE
# =========================================================

if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = "NVDA"


# =========================================================
# ACTIVE US STOCK UNIVERSE
#
# This is a large list of liquid and actively traded
# NASDAQ and NYSE stocks.
#
# We can expand this later.
# =========================================================

STOCKS = [

    # Technology / Mega Cap
    "AAPL", "MSFT", "NVDA", "AMD", "AVGO",
    "GOOGL", "GOOG", "META", "AMZN", "TSLA",
    "NFLX", "ORCL", "CRM", "ADBE", "INTC",
    "QCOM", "MU", "SMCI", "ARM", "PLTR",

    # Finance / Trading
    "HOOD", "SOFI", "AFRM", "UPST", "PYPL",
    "COIN", "MSTR", "IBKR", "FUTU", "NU",

    # AI / Quantum
    "AI", "SOUN", "BBAI", "PATH", "IONQ",
    "RGTI", "QBTS", "QUBT",

    # Crypto / Bitcoin
    "MARA", "RIOT", "CLSK", "CIFR",
    "IREN", "BTDR", "HUT",

    # EV
    "RIVN", "LCID", "NIO", "XPEV",
    "LI", "NKLA", "CHPT",

    # Semiconductors
    "AMAT", "LRCX", "KLAC", "MRVL",
    "ON", "WOLF", "COHR",

    # Energy
    "SMR", "OKLO", "UEC", "UUUU",
    "CCJ", "URA",

    # Space / Defence
    "RKLB", "ASTS", "LUNR", "RDW",
    "KTOS", "LMT", "NOC",

    # Biotech / Healthcare
    "MRNA", "BNTX", "CRSP", "RXRX",
    "TEM", "HIMS",

    # Retail / Consumer
    "WMT", "COST", "TGT", "NKE",
    "LULU", "CAVA", "CMG",

    # Internet / Communication
    "RDDT", "SNAP", "PINS", "ROKU",
    "UBER", "LYFT", "DASH",

    # Banks
    "JPM", "BAC", "C", "WFC",
    "GS", "MS",

    # Industrial
    "BA", "GE", "CAT", "DE",

    # High Activity Stocks
    "GME", "AMC", "PLUG", "OPEN",
    "JOBY", "ACHR", "LAES",

    # ETFs often useful for market direction
    "SPY", "QQQ", "IWM"
]


# =========================================================
# DOWNLOAD STOCK DATA
# =========================================================

@st.cache_data(ttl=45)

def get_market_data():

    results = []

    try:

        data = yf.download(
            STOCKS,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True
        )

        for ticker in STOCKS:

            try:

                stock_data = data[ticker].dropna()

                if len(stock_data) < 2:
                    continue

                previous_close = float(
                    stock_data["Close"].iloc[-2]
                )

                current_price = float(
                    stock_data["Close"].iloc[-1]
                )

                volume = int(
                    stock_data["Volume"].iloc[-1]
                )

                if previous_close <= 0:
                    continue

                change_percent = (
                    (
                        current_price
                        - previous_close
                    )
                    / previous_close
                ) * 100

                results.append(
                    {
                        "Ticker": ticker,
                        "Price": round(
                            current_price,
                            2
                        ),
                        "Change %": round(
                            change_percent,
                            2
                        ),
                        "Volume": volume
                    }
                )

            except Exception:
                continue

    except Exception as error:

        st.error(
            f"Market data error: {error}"
        )

    return pd.DataFrame(results)


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div style="
        font-size:26px;
        font-weight:700;
        margin-bottom:0px;
    ">
        📈 US STOCK SCREENER
    </div>
    """,
    unsafe_allow_html=True
)

st.caption(
    f"Active US Stocks • Auto Refresh: "
    f"{AUTO_REFRESH_SECONDS} seconds"
)


# =========================================================
# FILTERS
# =========================================================

with st.expander("⚙ Filters"):

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        min_price = st.number_input(
            "Minimum Price",
            min_value=0.0,
            value=1.0,
            step=0.50
        )

    with col2:

        max_price = st.number_input(
            "Maximum Price",
            min_value=0.0,
            value=1000.0,
            step=10.0
        )

    with col3:

        min_change = st.number_input(
            "Minimum Change %",
            value=0.0,
            step=0.50
        )

    with col4:

        min_volume = st.number_input(
            "Minimum Volume",
            min_value=0,
            value=100000,
            step=50000
        )


# =========================================================
# LOAD MARKET DATA
# =========================================================

with st.spinner("Scanning US stocks..."):

    df = get_market_data()


# =========================================================
# FILTER DATA
# =========================================================

if df.empty:

    st.warning(
        "No market data is currently available."
    )

    st.stop()


filtered_df = df.copy()

filtered_df = filtered_df[
    (filtered_df["Price"] >= min_price)
    &
    (filtered_df["Price"] <= max_price)
    &
    (filtered_df["Change %"] >= min_change)
    &
    (filtered_df["Volume"] >= min_volume)
]


# =========================================================
# SORT BY MOMENTUM
# =========================================================

filtered_df = filtered_df.sort_values(
    by="Change %",
    ascending=False
)


# =========================================================
# MAIN LAYOUT
# 35% LEFT / 65% RIGHT
# =========================================================

left_col, right_col = st.columns(
    [35, 65],
    gap="small"
)


# =========================================================
# LEFT SIDE
# STOCK SCANNER
# =========================================================

with left_col:

    st.markdown(
        f"### Stocks ({len(filtered_df)})"
    )

    # Only show first 30 to keep screen clean
    display_df = filtered_df.head(30)

    if display_df.empty:

        st.warning(
            "No stocks match the filters."
        )

    else:

        for _, row in display_df.iterrows():

            ticker = row["Ticker"]

            price = row["Price"]

            change = row["Change %"]

            volume = row["Volume"]

            if change >= 0:
                icon = "🟢"
            else:
                icon = "🔴"

            button_text = (
                f"{icon} {ticker} | "
                f"${price:.2f} | "
                f"{change:+.2f}%"
            )

            if st.button(
                button_text,
                key=f"stock_{ticker}",
                use_container_width=True
            ):

                st.session_state.selected_stock = ticker

                st.rerun()


# =========================================================
# RIGHT SIDE
# TRADINGVIEW CHART
# =========================================================

with right_col:

    selected = st.session_state.selected_stock

    st.markdown(
        f"### {selected}"
    )

    tradingview_html = f"""
    <div
        style="
            width:100%;
            height:calc(100vh - 150px);
            min-height:600px;
        "
    >

        <iframe

            src="https://www.tradingview.com/widgetembed/?symbol={selected}&interval=5&hidesidetoolbar=1&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=%5B%5D&theme=light&style=1&withdateranges=1"

            style="
                width:100%;
                height:100%;
                border:none;
            "

            frameborder="0"

            allowtransparency="true">

        </iframe>

    </div>
    """

    components.html(
        tradingview_html,
        height=650
    )


# =========================================================
# STATUS BAR
# =========================================================

current_time = datetime.now().strftime(
    "%H:%M:%S"
)

st.markdown(
    f"""
    <div style="
        text-align:center;
        font-size:11px;
        color:gray;
        margin-top:2px;
    ">

        🔄 Auto ON |
        Updated: {current_time} |
        Scanned: {len(STOCKS)} stocks |
        Results: {len(filtered_df)}

    </div>
    """,
    unsafe_allow_html=True
)
