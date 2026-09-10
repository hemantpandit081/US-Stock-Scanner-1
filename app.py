import streamlit as st
import pandas as pd
import yfinance as yf
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="US Momentum Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# CSS
# =========================================================

st.markdown("""
<style>

.block-container {
    padding-top: 0.5rem;
    padding-left: 0.6rem;
    padding-right: 0.6rem;
    padding-bottom: 0rem;
}

[data-testid="stSidebar"] {
    width: 280px;
}

div[data-testid="column"] {
    padding-left: 3px;
    padding-right: 3px;
}

.stock-row {
    font-size: 12px;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# 30 STOCKS
# =========================================================

STOCKS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META",
    "GOOGL", "GOOG", "TSLA", "AVGO", "AMD",
    "NFLX", "INTC", "MU", "QCOM", "AMAT",
    "ARM", "PLTR", "SMCI", "COIN", "HOOD",
    "SOFI", "BAC", "JPM", "WMT", "COST",
    "UBER", "SHOP", "PDD", "NIO", "RIVN"
]


# =========================================================
# SETTINGS
# =========================================================

SETTINGS_FILE = "scanner_settings.json"

DEFAULT_SETTINGS = {
    "min_price": 1.0,
    "max_price": 1000.0,
    "min_volume": 100000,
    "min_rvol": 1.5,
    "min_change": 1.0,
    "min_dollar_volume": 1000000,
    "repeat_tolerance": 0.90,
    "refresh_seconds": 60,
    "auto_scan": True,
    "chart_interval": "1"
}


def load_settings():

    if os.path.exists(SETTINGS_FILE):

        try:
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)

            result = DEFAULT_SETTINGS.copy()
            result.update(saved)

            return result

        except:
            pass

    return DEFAULT_SETTINGS.copy()


def save_settings():

    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)


settings = load_settings()


# =========================================================
# SESSION STATE
# =========================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "AAPL"

if "previous_volumes" not in st.session_state:
    st.session_state.previous_volumes = {}

if "scan_results" not in st.session_state:
    st.session_state.scan_results = pd.DataFrame()


# =========================================================
# TIME
# =========================================================

NY_TZ = ZoneInfo("America/New_York")


def market_open():

    now = datetime.now(NY_TZ)

    if now.weekday() >= 5:
        return False

    minutes = now.hour * 60 + now.minute

    return 570 <= minutes <= 960


# =========================================================
# GET INTRADAY DATA
# =========================================================

def get_intraday(symbol):

    try:

        df = yf.download(
            symbol,
            period="1d",
            interval="1m",
            auto_adjust=False,
            prepost=False,
            progress=False,
            threads=False
        )

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df.dropna()

    except:
        return None


# =========================================================
# GET DAILY DATA
# =========================================================

def get_daily(symbol):

    try:

        df = yf.download(
            symbol,
            period="20d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if df is None or df.empty:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        return df.dropna()

    except:
        return None


# =========================================================
# REPEAT VOLUME
# =========================================================

def repeat_volume(symbol, current_volume):

    previous = st.session_state.previous_volumes.get(symbol)

    signal = False

    if previous is not None and previous > 0:

        ratio = current_volume / previous

        tolerance = settings["repeat_tolerance"]

        if ratio >= tolerance:
            signal = True

    st.session_state.previous_volumes[symbol] = current_volume

    return signal


# =========================================================
# SCANNER
# =========================================================

def scan_stocks():

    results = []

    for symbol in STOCKS:

        try:

            intraday = get_intraday(symbol)

            if intraday is None or intraday.empty:
                continue

            daily = get_daily(symbol)

            if daily is None or daily.empty:
                continue

            # ---------------------------------------------
            # PRICE
            # ---------------------------------------------

            price = float(intraday["Close"].iloc[-1])

            # ---------------------------------------------
            # VOLUME
            # ---------------------------------------------

            volume = float(
                intraday["Volume"].fillna(0).sum()
            )

            # ---------------------------------------------
            # PREVIOUS CLOSE
            # ---------------------------------------------

            if len(daily) >= 2:
                previous_close = float(
                    daily["Close"].iloc[-2]
                )
            else:
                previous_close = price

            # ---------------------------------------------
            # CHANGE
            # ---------------------------------------------

            if previous_close > 0:

                change = (
                    (price - previous_close)
                    / previous_close
                    * 100
                )

            else:

                change = 0

            # ---------------------------------------------
            # AVERAGE VOLUME
            # ---------------------------------------------

            if len(daily) >= 6:

                avg_volume = float(
                    daily["Volume"].iloc[-6:-1].mean()
                )

            else:

                avg_volume = float(
                    daily["Volume"].mean()
                )

            # ---------------------------------------------
            # RVOL
            # ---------------------------------------------

            if avg_volume > 0:
                rvol = volume / avg_volume
            else:
                rvol = 0

            # ---------------------------------------------
            # DOLLAR VOLUME
            # ---------------------------------------------

            dollar_volume = price * volume

            # ---------------------------------------------
            # REPEAT
            # ---------------------------------------------

            repeat = repeat_volume(
                symbol,
                volume
            )

            # ---------------------------------------------
            # FILTERS
            # ---------------------------------------------

            if price < settings["min_price"]:
                continue

            if price > settings["max_price"]:
                continue

            if volume < settings["min_volume"]:
                continue

            if rvol < settings["min_rvol"]:
                continue

            if change < settings["min_change"]:
                continue

            if dollar_volume < settings["min_dollar_volume"]:
                continue

            results.append({
                "Symbol": symbol,
                "Price": price,
                "Change": change,
                "RVOL": rvol,
                "Volume": volume,
                "Dollar": dollar_volume,
                "Repeat": repeat
            })

        except:
            continue

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    df = df.sort_values(
        ["Repeat", "RVOL", "Change"],
        ascending=[False, False, False]
    )

    return df


# =========================================================
# SIDEBAR FILTERS
# =========================================================

with st.sidebar:

    st.title("⚙️ Filters")

    settings["min_price"] = st.number_input(
        "Minimum Price",
        value=float(settings["min_price"])
    )

    settings["max_price"] = st.number_input(
        "Maximum Price",
        value=float(settings["max_price"])
    )

    settings["min_volume"] = st.number_input(
        "Minimum Volume",
        value=int(settings["min_volume"]),
        step=10000
    )

    settings["min_rvol"] = st.number_input(
        "Minimum RVOL",
        value=float(settings["min_rvol"]),
        step=0.1
    )

    settings["min_change"] = st.number_input(
        "Minimum % Change",
        value=float(settings["min_change"]),
        step=0.5
    )

    settings["min_dollar_volume"] = st.number_input(
        "Minimum Dollar Volume",
        value=int(settings["min_dollar_volume"]),
        step=100000
    )

    settings["repeat_tolerance"] = st.slider(
        "Repeat Volume",
        0.50,
        1.00,
        float(settings["repeat_tolerance"]),
        0.01
    )

    settings["refresh_seconds"] = st.number_input(
        "Refresh Seconds",
        10,
        3600,
        int(settings["refresh_seconds"]),
        10
    )

    settings["chart_interval"] = st.selectbox(
        "Chart Interval",
        ["1", "5", "15", "30", "60", "D"]
    )

    settings["auto_scan"] = st.checkbox(
        "Auto Scan",
        value=bool(settings["auto_scan"])
    )

    if st.button("💾 Save Filters"):
        save_settings()
        st.success("Saved")


# =========================================================
# HEADER
# =========================================================

header1, header2, header3 = st.columns([5, 2, 2])

with header1:
    st.markdown("## 📈 US Momentum Stock Scanner")

with header2:

    if market_open():
        st.success("🟢 Market Open")
    else:
        st.info("⚪ Market Closed")

with header3:

    if st.button(
        "🔄 Scan Now",
        use_container_width=True
    ):

        st.session_state.scan_results = scan_stocks()


# =========================================================
# FIRST SCAN
# =========================================================

if st.session_state.scan_results.empty:

    st.session_state.scan_results = scan_stocks()


df = st.session_state.scan_results


# =========================================================
# EXACT 35 / 65 LAYOUT
# =========================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# =========================================================
# 35% STOCK LIST
# =========================================================

with left:

    st.markdown("### 📋 Stocks")

    if df.empty:

        st.info(
            "No stocks match the filters."
        )

    else:

        # Header
        h1, h2, h3, h4, h5 = st.columns(
            [1.4, 1.2, 1, 1, 1.2]
        )

        h1.caption("Symbol")
        h2.caption("LTP")
        h3.caption("%")
        h4.caption("RVOL")
        h5.caption("$Vol")

        for _, row in df.iterrows():

            symbol = row["Symbol"]

            c1, c2, c3, c4, c5 = st.columns(
                [1.4, 1.2, 1, 1, 1.2]
            )

            with c1:

                if row["Repeat"]:
                    label = f"■ {symbol}"
                else:
                    label = symbol

                if st.button(
                    label,
                    key=f"select_{symbol}",
                    use_container_width=True
                ):

                    st.session_state.selected_symbol = symbol

            with c2:

                st.caption(
                    f"${row['Price']:.2f}"
                )

            with c3:

                st.caption(
                    f"{row['Change']:.1f}%"
                )

            with c4:

                st.caption(
                    f"{row['RVOL']:.1f}x"
                )

            with c5:

                dollar = row["Dollar"]

                if dollar >= 1_000_000_000:
                    text = f"${dollar/1_000_000_000:.1f}B"

                elif dollar >= 1_000_000:
                    text = f"${dollar/1_000_000:.1f}M"

                else:
                    text = f"${dollar/1_000:.0f}K"

                st.caption(text)


# =========================================================
# 65% TRADINGVIEW
# =========================================================

with right:

    symbol = st.session_state.selected_symbol

    interval = settings["chart_interval"]

    st.markdown(
        f"### 📊 {symbol}"
    )

    # TradingView iframe
    tradingview_url = (
        "https://www.tradingview.com/widgetembed/"
        "?frameElementId=tradingview_chart"
        f"&symbol=NASDAQ%3A{symbol}"
        f"&interval={interval}"
        "&hide_side_toolbar=0"
        "&allow_symbol_change=1"
        "&save_image=1"
        "&hide_volume=0"
        "&theme=dark"
        "&style=1"
        "&timezone=America%2FNew_York"
        "&withdateranges=1"
        "&hide_legend=0"
        "&locale=en"
    )

    html = f"""
    <iframe
        id="tradingview_chart"
        src="{tradingview_url}"
        style="
            width:100%;
            height:700px;
            border:0;
        "
        allowtransparency="true"
        frameborder="0"
        scrolling="no">
    </iframe>
    """

    components.html(
        html,
        height=720,
        scrolling=False
    )


# =========================================================
# AUTO REFRESH
# =========================================================

if settings["auto_scan"]:

    seconds = int(
        settings["refresh_seconds"]
    )

    st.markdown(
        f"""
        <script>
        setTimeout(function() {{
            window.parent.location.reload();
        }}, {seconds * 1000});
        </script>
        """,
        unsafe_allow_html=True
    )
