import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components


# =========================================================
# PAGE CONFIG
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
    padding-top: 0.7rem;
    padding-bottom: 0rem;
    padding-left: 0.7rem;
    padding-right: 0.7rem;
}

[data-testid="stSidebar"] {
    width: 280px;
}

.stock-button button {
    width: 100%;
    text-align: left;
}

div[data-testid="column"] {
    padding-left: 3px;
    padding-right: 3px;
}

.small-text {
    font-size: 11px;
}

.repeat-square {
    font-size: 15px;
    color: black;
    margin-right: 4px;
}

.scanner-header {
    font-size: 12px;
    font-weight: 600;
    padding-bottom: 4px;
    border-bottom: 1px solid #cccccc;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# FIXED 30 STOCKS
# =========================================================

STOCKS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "META",
    "GOOGL",
    "GOOG",
    "TSLA",
    "AVGO",
    "AMD",
    "NFLX",
    "INTC",
    "MU",
    "QCOM",
    "AMAT",
    "ARM",
    "PLTR",
    "SMCI",
    "COIN",
    "HOOD",
    "SOFI",
    "BAC",
    "JPM",
    "WMT",
    "COST",
    "UBER",
    "SHOP",
    "PDD",
    "NIO",
    "RIVN"
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
                data = json.load(f)

            settings = DEFAULT_SETTINGS.copy()
            settings.update(data)

            return settings

        except Exception:
            pass

    return DEFAULT_SETTINGS.copy()


def save_settings(settings):

    try:

        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)

    except Exception:
        pass


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


def ny_time():

    return datetime.now(NY_TZ)


def market_is_open():

    now = ny_time()

    if now.weekday() >= 5:
        return False

    current_time = now.hour * 60 + now.minute

    market_open = 9 * 60 + 30
    market_close = 16 * 60

    return market_open <= current_time <= market_close


# =========================================================
# YFINANCE DATA
# =========================================================

def get_symbol_data(symbol):

    try:

        data = yf.download(
            tickers=symbol,
            period="1d",
            interval="1m",
            auto_adjust=False,
            prepost=False,
            progress=False,
            threads=False
        )

        if data is None or data.empty:
            return None

        if isinstance(data.columns, pd.MultiIndex):

            try:
                data.columns = data.columns.get_level_values(0)
            except Exception:
                pass

        data = data.dropna()

        return data

    except Exception:

        return None


# =========================================================
# DAILY DATA
# =========================================================

def get_daily_data(symbol):

    try:

        data = yf.download(
            tickers=symbol,
            period="20d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if data is None or data.empty:
            return None

        if isinstance(data.columns, pd.MultiIndex):

            try:
                data.columns = data.columns.get_level_values(0)
            except Exception:
                pass

        return data.dropna()

    except Exception:

        return None


# =========================================================
# REPEAT VOLUME
# =========================================================

def detect_repeat_volume(symbol, current_volume, tolerance):

    previous_volume = st.session_state.previous_volumes.get(symbol)

    signal = False
    near_same = False
    higher = False

    if previous_volume is not None and previous_volume > 0:

        ratio = current_volume / previous_volume

        lower_limit = tolerance
        upper_limit = 1 / tolerance

        if lower_limit <= ratio <= upper_limit:
            near_same = True

        if current_volume > previous_volume:
            higher = True

        if near_same or higher:
            signal = True

    st.session_state.previous_volumes[symbol] = current_volume

    return signal, near_same, higher


# =========================================================
# SCANNER
# =========================================================

def run_scanner():

    results = []

    for symbol in STOCKS:

        try:

            intraday = get_symbol_data(symbol)

            if intraday is None or intraday.empty:
                continue

            daily = get_daily_data(symbol)

            if daily is None or daily.empty:
                continue

            # ---------------------------------------------
            # LTP
            # ---------------------------------------------

            ltp = float(intraday["Close"].iloc[-1])

            # ---------------------------------------------
            # SESSION VOLUME
            # ---------------------------------------------

            current_volume = float(intraday["Volume"].fillna(0).sum())

            # ---------------------------------------------
            # PREVIOUS CLOSE
            # ---------------------------------------------

            if len(daily) >= 2:

                previous_close = float(
                    daily["Close"].iloc[-2]
                )

            else:

                previous_close = ltp

            # ---------------------------------------------
            # CHANGE %
            # ---------------------------------------------

            if previous_close > 0:

                change_pct = (
                    (ltp - previous_close)
                    / previous_close
                    * 100
                )

            else:

                change_pct = 0

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

                rvol = current_volume / avg_volume

            else:

                rvol = 0

            # ---------------------------------------------
            # DOLLAR VOLUME
            # ---------------------------------------------

            dollar_volume = ltp * current_volume

            # ---------------------------------------------
            # REPEAT VOLUME
            # ---------------------------------------------

            repeat_signal, near_same, higher = detect_repeat_volume(
                symbol,
                current_volume,
                settings["repeat_tolerance"]
            )

            # ---------------------------------------------
            # FILTERS
            # ---------------------------------------------

            if ltp < settings["min_price"]:
                continue

            if ltp > settings["max_price"]:
                continue

            if current_volume < settings["min_volume"]:
                continue

            if rvol < settings["min_rvol"]:
                continue

            if change_pct < settings["min_change"]:
                continue

            if dollar_volume < settings["min_dollar_volume"]:
                continue

            # ---------------------------------------------
            # ADD RESULT
            # ---------------------------------------------

            results.append({
                "Symbol": symbol,
                "LTP": ltp,
                "Change": change_pct,
                "RVOL": rvol,
                "Volume": current_volume,
                "Dollar Volume": dollar_volume,
                "Repeat": repeat_signal,
                "Near Same": near_same,
                "Higher": higher
            })

        except Exception:
            continue

    # =====================================================
    # DATAFRAME
    # =====================================================

    if not results:

        return pd.DataFrame(
            columns=[
                "Symbol",
                "LTP",
                "Change",
                "RVOL",
                "Volume",
                "Dollar Volume",
                "Repeat",
                "Near Same",
                "Higher"
            ]
        )

    df = pd.DataFrame(results)

    df = df.sort_values(
        by=["Repeat", "RVOL", "Change"],
        ascending=[False, False, False]
    )

    return df


# =========================================================
# SIDEBAR - ONLY SETTINGS
# =========================================================

with st.sidebar:

    st.title("⚙️ Scanner Filters")

    st.caption("Filters are hidden from the main dashboard.")

    st.divider()

    settings["min_price"] = st.number_input(
        "Minimum Price",
        min_value=0.0,
        value=float(settings["min_price"]),
        step=1.0
    )

    settings["max_price"] = st.number_input(
        "Maximum Price",
        min_value=1.0,
        value=float(settings["max_price"]),
        step=10.0
    )

    settings["min_volume"] = st.number_input(
        "Minimum Volume",
        min_value=0,
        value=int(settings["min_volume"]),
        step=10000
    )

    settings["min_rvol"] = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=float(settings["min_rvol"]),
        step=0.1
    )

    settings["min_change"] = st.number_input(
        "Minimum % Change",
        min_value=0.0,
        value=float(settings["min_change"]),
        step=0.5
    )

    settings["min_dollar_volume"] = st.number_input(
        "Minimum Dollar Volume",
        min_value=0,
        value=int(settings["min_dollar_volume"]),
        step=100000
    )

    settings["repeat_tolerance"] = st.slider(
        "Repeat Volume Tolerance",
        min_value=0.50,
        max_value=1.00,
        value=float(settings["repeat_tolerance"]),
        step=0.01
    )

    settings["refresh_seconds"] = st.number_input(
        "Refresh Seconds",
        min_value=10,
        max_value=3600,
        value=int(settings["refresh_seconds"]),
        step=10
    )

    settings["chart_interval"] = st.selectbox(
        "Chart Interval",
        ["1", "5", "15", "30", "60", "D"],
        index=["1", "5", "15", "30", "60", "D"].index(
            settings["chart_interval"]
        )
    )

    settings["auto_scan"] = st.checkbox(
        "Auto Scan",
        value=bool(settings["auto_scan"])
    )

    if st.button("💾 Save Filters", use_container_width=True):

        save_settings(settings)

        st.success("Saved")


# =========================================================
# TOP BAR
# =========================================================

top1, top2, top3 = st.columns([5, 2, 2])

with top1:

    st.markdown(
        "## 📈 US Momentum Stock Scanner"
    )

with top2:

    if market_is_open():

        st.success("🟢 Market Open")

    else:

        st.info("⚪ Market Closed")


with top3:

    if st.button("🔄 Scan Now", use_container_width=True):

        st.session_state.scan_results = run_scanner()


# =========================================================
# FILTER BUTTON
# =========================================================

with st.expander("⚙️ Filters / Settings", expanded=False):

    st.write(
        "Filters are available in the sidebar. "
        "Open the sidebar only when you want to change them."
    )


# =========================================================
# SCAN
# =========================================================

if st.session_state.scan_results.empty:

    st.session_state.scan_results = run_scanner()


df = st.session_state.scan_results


# =========================================================
# MAIN LAYOUT
# EXACTLY 35% STOCK LIST / 65% CHART
# =========================================================

left_col, right_col = st.columns(
    [35, 65],
    gap="small"
)


# =========================================================
# LEFT - STOCK LIST 35%
# =========================================================

with left_col:

    st.markdown("### 📋 Stocks")

    st.markdown(
        """
        <div class="scanner-header">
        Time &nbsp;&nbsp;&nbsp; Symbol &nbsp;&nbsp;&nbsp; LTP &nbsp;&nbsp; % &nbsp;&nbsp; RVOL &nbsp;&nbsp; $Vol
        </div>
        """,
        unsafe_allow_html=True
    )

    if df.empty:

        st.info("No stocks match the current filters.")

    else:

        for _, row in df.iterrows():

            symbol = row["Symbol"]

            repeat = bool(row["Repeat"])

            if repeat:

                square = "■"

            else:

                square = ""

            c1, c2, c3, c4, c5, c6 = st.columns(
                [0.8, 1.5, 1.0, 0.9, 1.0, 1.3]
            )

            with c1:

                st.caption(
                    datetime.now().strftime("%H:%M")
                )

            with c2:

                if st.button(
                    f"{square} {symbol}",
                    key=f"stock_{symbol}",
                    use_container_width=True
                ):

                    st.session_state.selected_symbol = symbol

            with c3:

                st.caption(
                    f"${row['LTP']:.2f}"
                )

            with c4:

                st.caption(
                    f"{row['Change']:.1f}%"
                )

            with c5:

                st.caption(
                    f"{row['RVOL']:.1f}x"
                )

            with c6:

                dollar = row["Dollar Volume"]

                if dollar >= 1_000_000_000:

                    text = f"${dollar/1_000_000_000:.1f}B"

                elif dollar >= 1_000_000:

                    text = f"${dollar/1_000_000:.1f}M"

                else:

                    text = f"${dollar/1_000:.0f}K"

                st.caption(text)


# =========================================================
# RIGHT - TRADINGVIEW CHART 65%
# =========================================================

with right_col:

    symbol = st.session_state.selected_symbol

    interval = settings["chart_interval"]

    st.markdown(
        f"### 📊 {symbol}"
    )

    chart_html = f"""
    <div class="tradingview-widget-container"
         style="height:700px;width:100%;">

      <div id="tradingview_chart"
           style="height:700px;width:100%;"></div>

      <script type="text/javascript"
              src="https://s3.tradingview.com/tv.js">
      </script>

      <script type="text/javascript">

      new TradingView.widget({{
          "autosize": true,
          "symbol": "NASDAQ:{symbol}",
          "interval": "{interval}",
          "timezone": "America/New_York",
          "theme": "dark",
          "style": "1",
          "locale": "en",
          "enable_publishing": false,
          "allow_symbol_change": true,
          "withdateranges": true,
          "hide_side_toolbar": false,
          "hide_top_toolbar": false,
          "save_image": true,
          "hide_volume": false,
          "hide_legend": false,
          "calendar": false,
          "studies": [],
          "support_host": "https://www.tradingview.com"
      }});

      </script>

    </div>
    """

    components.html(
        chart_html,
        height=720
    )


# =========================================================
# AUTO REFRESH
# =========================================================

if settings["auto_scan"]:

    refresh_seconds = int(
        settings["refresh_seconds"]
    )

    st.markdown(
        f"""
        <div style="
            text-align:center;
            font-size:11px;
            color:gray;
            margin-top:3px;
        ">
        Auto scan: every {refresh_seconds} seconds
        </div>
        """,
        unsafe_allow_html=True
    )

    # Streamlit rerun timer
    st.markdown(
        f"""
        <script>
        setTimeout(function(){{
            window.parent.location.reload();
        }}, {refresh_seconds * 1000});
        </script>
        """,
        unsafe_allow_html=True
    )
