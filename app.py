from datetime import datetime
import json
import os
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

# ============================================================
# WEBULL IMPORTS
# ============================================================
from webull.core.client import ApiClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan
from webull.data.data_client import DataClient

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="US Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# CUSTOM CSS (FIT TO SINGLE SCREEN / NO PAGE SCROLL)
# ============================================================
st.markdown(
    """
<style>
/* Hide Streamlit default elements */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
header { visibility: hidden; }

/* Lock viewport page scrolling */
html, body, [data-testid="stAppViewContainer"] {
    height: 100vh;
    overflow: hidden !important;
}

.block-container {
    padding-top: 0.2rem;
    padding-bottom: 0.2rem;
    padding-left: 0.5rem;
    padding-right: 0.5rem;
    max-height: 98vh;
}

/* Scanner Column Styling */
.scanner-title {
    font-size: 18px;
    font-weight: 700;
    margin-bottom: 2px;
    line-height: 1.2;
}

/* Tabs & Container Height Constraints */
[data-testid="stTab"] {
    padding: 2px 8px !important;
}

[data-testid="stTabPanel"] {
    max-height: 82vh;
    overflow-y: auto !important;
    padding-right: 4px;
}

/* Custom scrollbars */
::-webkit-scrollbar {
    width: 4px;
}
::-webkit-scrollbar-thumb {
    background: #444;
    border-radius: 2px;
}

.green { color: #00c853; }
.red { color: #ff5252; }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# CONSTANTS
# ============================================================
SETTINGS_FILE = "scanner_settings.json"
WATCHLIST_FILE = "watchlist.json"
NY = ZoneInfo("America/New_York")

DEFAULT_SYMBOLS = [
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
    "RIVN",
    "MSTR",
    "CRWD",
    "SNOW",
    "RBLX",
    "DKNG",
    "MARA",
    "RIOT",
    "TQQQ",
    "SPY",
    "QQQ",
]

DEFAULT_SETTINGS = {
    "min_price": 1.0,
    "max_price": 1000.0,
    "min_volume": 100000,
    "min_rvol": 1.5,
    "min_change": 1.0,
    "min_dollar_volume": 1000000,
    "repeat_tolerance": 0.90,
    "refresh_seconds": 60,
    "chart_interval": "1",
    "auto_scan": True,
}


# ============================================================
# FILE HELPERS
# ============================================================
def load_json(filename, default):
    if not os.path.exists(filename):
        return default.copy() if isinstance(default, dict) else list(default)
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except Exception:
        return default.copy() if isinstance(default, dict) else list(default)


def save_json(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        st.error(f"Could not save {filename}: {e}")


# ============================================================
# SESSION STATE
# ============================================================
if "settings" not in st.session_state:
    st.session_state.settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)

if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_json(WATCHLIST_FILE, [])

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "AAPL"

if "regular_results" not in st.session_state:
    st.session_state.regular_results = pd.DataFrame()

if "watchlist_results" not in st.session_state:
    st.session_state.watchlist_results = pd.DataFrame()

if "volume_history" not in st.session_state:
    st.session_state.volume_history = {}


# ============================================================
# WEBULL CONNECTION
# ============================================================
@st.cache_resource
def get_webull_client():
    app_key = st.secrets.get("WEBULL_APP_KEY", "")
    app_secret = st.secrets.get("WEBULL_APP_SECRET", "")
    if not app_key or not app_secret:
        return None
    api_client = ApiClient(app_key, app_secret, "us")
    api_client.add_endpoint("us", "api.webull.com")
    return DataClient(api_client)


webull_client = get_webull_client()

# ============================================================
# WEBULL HISTORICAL DATA & ANALYSIS
# ============================================================
def get_history(symbol, timespan=Timespan.M1.name):
    if webull_client is None:
        return None
    try:
        response = webull_client.market_data.get_history_bar(
            symbol, Category.US_STOCK.name, timespan
        )
        if response.status_code != 200:
            return None
        data = response.json()
        if isinstance(data, dict):
            data = data.get("data", data.get("items", []))
        if not isinstance(data, list):
            return None
        df = pd.DataFrame(data)
        return normalize_bars(df) if not df.empty else None
    except Exception:
        return None


def normalize_bars(df):
    rename_map = {}
    possible_columns = {
        "open": ["open", "open_price"],
        "high": ["high", "high_price"],
        "low": ["low", "low_price"],
        "close": ["close", "close_price"],
        "volume": ["volume", "vol"],
    }
    for target, possibilities in possible_columns.items():
        for col in possibilities:
            if col in df.columns:
                rename_map[col] = target
                break
    df = df.rename(columns=rename_map)
    for col in ["close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close", "volume"])


def analyze_stock(symbol):
    intraday = get_history(symbol, Timespan.M1.name)
    if intraday is None or intraday.empty:
        return None

    price = float(intraday.iloc[-1]["close"])
    current_volume = float(intraday["volume"].sum())

    daily_df = get_history(symbol, Timespan.D1.name)
    rvol, change = 0.0, 0.0

    if daily_df is not None and not daily_df.empty and len(daily_df) >= 5:
        avg_vol = float(daily_df["volume"].tail(20).mean())
        if avg_vol > 0:
            rvol = current_volume / avg_vol

        prev_close = float(daily_df.iloc[-2]["close"])
        if prev_close > 0:
            change = ((price - prev_close) / prev_close) * 100.0

    previous = st.session_state.volume_history.get(symbol)
    repeat = (
        True
        if previous
        and (
            current_volume / previous
            >= st.session_state.settings["repeat_tolerance"]
        )
        else False
    )
    st.session_state.volume_history[symbol] = current_volume

    return {
        "Time": datetime.now(NY).strftime("%H:%M:%S"),
        "Symbol": symbol,
        "Price": price,
        "Change %": change,
        "RVOL": rvol,
        "Volume": int(current_volume),
        "Dollar Volume": price * current_volume,
        "Repeat": repeat,
    }


def run_regular_scan():
    settings = st.session_state.settings
    rows = []
    for symbol in DEFAULT_SYMBOLS:
        res = analyze_stock(symbol)
        if res and (
            settings["min_price"] <= res["Price"] <= settings["max_price"]
        ):
            if (
                res["Volume"] >= settings["min_volume"]
                and res["RVOL"] >= settings["min_rvol"]
            ):
                if (
                    res["Change %"] >= settings["min_change"]
                    and res["Dollar Volume"] >= settings["min_dollar_volume"]
                ):
                    rows.append(res)
    return (
        pd.DataFrame(rows).sort_values(by="RVOL", ascending=False)
        if rows
        else pd.DataFrame()
    )


def run_watchlist_scan():
    rows = []
    for symbol in st.session_state.watchlist:
        res = analyze_stock(symbol)
        if res:
            rows.append(res)
    return (
        pd.DataFrame(rows).sort_values(by="RVOL", ascending=False)
        if rows
        else pd.DataFrame()
    )


# ============================================================
# TRADINGVIEW CHART COMPONENT
# ============================================================
def show_chart(symbol):
    interval = st.session_state.settings["chart_interval"]
    chart_url = (
        f"https://www.tradingview.com/widgetembed/?symbol={symbol or 'AAPL'}"
        f"&interval={interval}&hidetoptoolbar=0&symboledit=1&saveimage=0"
        "&toolbarbg=f1f3f6&theme=dark&style=1&timezone=America%2FNew_York"
    )
    # Scaled height fits nicely within full screen limits without page overflow
    st.components.v1.iframe(chart_url, height=880, scrolling=False)


# ============================================================
# LAYOUT STRUCTURE
# ============================================================
left, right = st.columns([32, 68], gap="small")

with left:
    st.markdown(
        '<div class="scanner-title">US STOCK SCANNER</div>',
        unsafe_allow_html=True,
    )

    if webull_client is None:
        st.warning("Configure WEBULL_APP_KEY / WEBULL_APP_SECRET.")

    tab1, tab2, tab3 = st.tabs(
        ["WATCHLIST", "REGULAR SCAN", "WATCHLIST SCAN"]
    )

    # ------------------ TAB 1: WATCHLIST ------------------
    with tab1:
        c_add1, c_add2 = st.columns([2.5, 1], gap="small")
        with c_add1:
            add_symbol = st.text_input(
                "Add Symbol",
                placeholder="e.g. NVDA",
                label_visibility="collapsed",
            ).upper()
        with c_add2:
            if st.button("Add", use_container_width=True) and add_symbol:
                if add_symbol not in st.session_state.watchlist:
                    st.session_state.watchlist.append(add_symbol)
                    save_json(WATCHLIST_FILE, st.session_state.watchlist)
                    st.session_state.selected_symbol = add_symbol
                    st.rerun()

        if not st.session_state.watchlist:
            st.info("Watchlist empty.")
        else:
            for symbol in st.session_state.watchlist:
                c1, c2 = st.columns([3, 1], gap="small")
                with c1:
                    if st.button(
                        symbol, key=f"wl_{symbol}", use_container_width=True
                    ):
                        st.session_state.selected_symbol = symbol
                        st.rerun()
                with c2:
                    if st.button("×", key=f"rem_{symbol}"):
                        st.session_state.watchlist.remove(symbol)
                        save_json(WATCHLIST_FILE, st.session_state.watchlist)
                        st.rerun()

    # ------------------ TAB 2: REGULAR SCAN ------------------
    with tab2:
        s = st.session_state.settings
        with st.expander("⚙️ Settings", expanded=False):
            s["min_price"] = st.number_input(
                "Min Price ($)", value=float(s["min_price"])
            )
            s["max_price"] = st.number_input(
                "Max Price ($)", value=float(s["max_price"])
            )
            s["min_volume"] = st.number_input(
                "Min Volume", value=int(s["min_volume"])
            )
            s["min_rvol"] = st.number_input(
                "Min RVOL", value=float(s["min_rvol"])
            )
            s["min_change"] = st.number_input(
                "Min Change %", value=float(s["min_change"])
            )
            s["chart_interval"] = st.selectbox(
                "Timeframe",
                ["1", "3", "5", "15", "60"],
                index=["1", "3", "5", "15", "60"].index(
                    str(s["chart_interval"])
                ),
            )
            s["auto_scan"] = st.checkbox("Auto Scan", value=s["auto_scan"])
            if st.button("Save Settings", use_container_width=True):
                save_json(SETTINGS_FILE, s)
                st.success("Saved.")

        if st.button("🚀 SCAN MARKET NOW", use_container_width=True):
            with st.spinner("Scanning..."):
                st.session_state.regular_results = run_regular_scan()

        df = st.session_state.regular_results
        if df.empty:
            st.info("No active market results.")
        else:
            for _, row in df.iterrows():
                sym = row["Symbol"]
                c1, c2, c3 = st.columns([1.5, 1.0, 1.0], gap="small")
                with c1:
                    if st.button(
                        sym, key=f"reg_{sym}", use_container_width=True
                    ):
                        st.session_state.selected_symbol = sym
                        st.rerun()
                with c2:
                    st.markdown(f"**{row['Change %']:+.2f}%**")
                with c3:
                    st.markdown(f"RVOL **{row['RVOL']:.2f}**")

    # ------------------ TAB 3: WATCHLIST STOCK SCAN ------------------
    with tab3:
        if not st.session_state.watchlist:
            st.warning("Add tickers in WATCHLIST tab.")
        else:
            if st.button("🔍 SCAN WATCHLIST", use_container_width=True):
                with st.spinner("Scanning..."):
                    st.session_state.watchlist_results = run_watchlist_scan()

            df_wl = st.session_state.watchlist_results
            if df_wl.empty:
                st.info("No scan results yet.")
            else:
                for _, row in df_wl.iterrows():
                    sym = row["Symbol"]
                    c1, c2, c3, c4 = st.columns(
                        [1.4, 1.0, 1.0, 0.6], gap="small"
                    )
                    with c1:
                        if st.button(
                            sym, key=f"wls_{sym}", use_container_width=True
                        ):
                            st.session_state.selected_symbol = sym
                            st.rerun()
                    with c2:
                        st.markdown(f"{row['Change %']:+.2f}%")
                    with c3:
                        st.markdown(f"RVOL {row['RVOL']:.2f}")
                    with c4:
                        repeat_color = (
                            '<span class="green">■</span>'
                            if row["Repeat"]
                            else '<span style="color:#555">■</span>'
                        )
                        st.markdown(repeat_color, unsafe_allow_html=True)

with right:
    show_chart(st.session_state.selected_symbol)

# ============================================================
# AUTOREFRESH ENGINE
# ============================================================
if st.session_state.settings.get("auto_scan", False):
    try:
        from streamlit_autorefresh import st_autorefresh

        st_autorefresh(
            interval=int(
                st.session_state.settings.get("refresh_seconds", 60) * 1000
            ),
            key="scanner_autorefresh",
        )
    except ImportError:
        pass
