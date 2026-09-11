import streamlit as st
import pandas as pd
import numpy as np
import json
import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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
    initial_sidebar_state="collapsed"
)

# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown("""
<style>

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

header {
    visibility: hidden;
}

.block-container {
    padding-top: 0.4rem;
    padding-left: 0.6rem;
    padding-right: 0.6rem;
}

.scanner-title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 5px;
}

.small-text {
    font-size: 11px;
    color: #888;
}

.stock-row {
    border-bottom: 1px solid #303030;
    padding: 6px 3px;
}

.stock-symbol {
    font-weight: 700;
    font-size: 14px;
}

.stock-name {
    font-size: 11px;
    color: #888;
}

.repeat-box {
    font-size: 13px;
    font-weight: 700;
}

.green {
    color: #00c853;
}

.red {
    color: #ff5252;
}

.tab-note {
    font-size: 11px;
    color: #888;
    margin-bottom: 5px;
}

</style>
""", unsafe_allow_html=True)

# ============================================================
# CONSTANTS
# ============================================================

SETTINGS_FILE = "scanner_settings.json"
WATCHLIST_FILE = "watchlist.json"

NY = ZoneInfo("America/New_York")

# ============================================================
# STARTER SYMBOL UNIVERSE
#
# IMPORTANT:
# Replace/expand this with your complete US universe later.
# ============================================================

DEFAULT_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META",
    "GOOGL", "GOOG", "TSLA", "AVGO", "AMD",
    "NFLX", "INTC", "MU", "QCOM", "AMAT",
    "ARM", "PLTR", "SMCI", "COIN", "HOOD",
    "SOFI", "BAC", "JPM", "WMT", "COST",
    "UBER", "SHOP", "PDD", "NIO", "RIVN",
    "MSTR", "CRWD", "SNOW", "RBLX", "DKNG",
    "MARA", "RIOT", "TQQQ", "SPY", "QQQ"
]

# ============================================================
# DEFAULT SETTINGS
# ============================================================

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
    "auto_scan": True
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
    st.session_state.settings = load_json(
        SETTINGS_FILE,
        DEFAULT_SETTINGS
    )

if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_json(
        WATCHLIST_FILE,
        []
    )

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "AAPL"

if "regular_results" not in st.session_state:
    st.session_state.regular_results = pd.DataFrame()

if "watchlist_results" not in st.session_state:
    st.session_state.watchlist_results = pd.DataFrame()

if "volume_history" not in st.session_state:
    st.session_state.volume_history = {}

if "last_scan_time" not in st.session_state:
    st.session_state.last_scan_time = None

# ============================================================
# WEBULL CONNECTION
# ============================================================

@st.cache_resource
def get_webull_client():

    app_key = st.secrets.get("WEBULL_APP_KEY", "")
    app_secret = st.secrets.get("WEBULL_APP_SECRET", "")

    if not app_key or not app_secret:
        return None

    api_client = ApiClient(
        app_key,
        app_secret,
        "us"
    )

    api_client.add_endpoint(
        "us",
        "api.webull.com"
    )

    return DataClient(api_client)


webull_client = get_webull_client()

# ============================================================
# WEBULL STATUS
# ============================================================

if webull_client is None:

    st.warning(
        "Webull API credentials are not configured. "
        "Add WEBULL_APP_KEY and WEBULL_APP_SECRET to "
        ".streamlit/secrets.toml."
    )


# ============================================================
# WEBULL HISTORICAL DATA
# ============================================================

def get_history(symbol, timespan=Timespan.M1.name, count=390):

    if webull_client is None:
        return None

    try:

        response = webull_client.market_data.get_history_bar(
            symbol,
            Category.US_STOCK.name,
            timespan
        )

        if response.status_code != 200:
            return None

        data = response.json()

        if isinstance(data, dict):

            # Webull may wrap bars in a data/list field
            if "data" in data:
                data = data["data"]

            elif "items" in data:
                data = data["items"]

        if not isinstance(data, list):
            return None

        df = pd.DataFrame(data)

        if df.empty:
            return None

        return normalize_bars(df)

    except Exception:
        return None


# ============================================================
# NORMALIZE WEBULL BARS
# ============================================================

def normalize_bars(df):

    rename_map = {}

    possible_columns = {
        "open": ["open", "open_price"],
        "high": ["high", "high_price"],
        "low": ["low", "low_price"],
        "close": ["close", "close_price"],
        "volume": ["volume", "vol"],
        "timestamp": [
            "timestamp",
            "time",
            "trade_time",
            "datetime"
        ]
    }

    for target, possibilities in possible_columns.items():

        for col in possibilities:

            if col in df.columns:
                rename_map[col] = target
                break

    df = df.rename(columns=rename_map)

    required = ["close", "volume"]

    for col in required:

        if col not in df.columns:
            return pd.DataFrame()

    for col in ["open", "high", "low", "close", "volume"]:

        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

    if "timestamp" in df.columns:

        try:
            df["timestamp"] = pd.to_datetime(
                df["timestamp"],
                errors="coerce",
                utc=True
            )
        except Exception:
            pass

    return df.dropna(subset=["close", "volume"])


# ============================================================
# GET CURRENT MARKET SNAPSHOT
# ============================================================

def get_snapshot(symbols):

    """
    Uses Webull historical 1-minute data to obtain the
    latest available bar.

    This function is deliberately isolated so that we can
    later replace it with Webull batch snapshot calls
    without changing the scanner UI.
    """

    results = []

    for symbol in symbols:

        df = get_history(
            symbol,
            Timespan.M1.name
        )

        if df is None or df.empty:
            continue

        latest = df.iloc[-1]

        price = float(latest["close"])
        volume = float(latest["volume"])

        results.append({
            "symbol": symbol,
            "price": price,
            "volume": volume
        })

    return pd.DataFrame(results)


# ============================================================
# DAILY DATA
# ============================================================

def get_daily_data(symbol):

    df = get_history(
        symbol,
        Timespan.D1.name
    )

    if df is None or df.empty:
        return None

    return df


# ============================================================
# CALCULATE RVOL
# ============================================================

def calculate_rvol(symbol, intraday_df):

    if intraday_df is None or intraday_df.empty:
        return 0.0

    today_volume = float(
        intraday_df["volume"].sum()
    )

    daily_df = get_daily_data(symbol)

    if daily_df is None or daily_df.empty:
        return 0.0

    daily_volumes = pd.to_numeric(
        daily_df["volume"],
        errors="coerce"
    ).dropna()

    if len(daily_volumes) < 5:
        return 0.0

    average_volume = float(
        daily_volumes.tail(20).mean()
    )

    if average_volume <= 0:
        return 0.0

    return today_volume / average_volume


# ============================================================
# CALCULATE PRICE CHANGE
# ============================================================

def calculate_change(symbol, current_price):

    daily_df = get_daily_data(symbol)

    if daily_df is None or daily_df.empty:
        return 0.0

    if len(daily_df) < 2:
        return 0.0

    previous_close = float(
        daily_df.iloc[-2]["close"]
    )

    if previous_close <= 0:
        return 0.0

    return (
        (current_price - previous_close)
        / previous_close
    ) * 100.0


# ============================================================
# REPEAT VOLUME
# ============================================================

def calculate_repeat_volume(
    symbol,
    current_volume,
    tolerance
):

    previous = st.session_state.volume_history.get(
        symbol
    )

    result = False

    if previous is not None and previous > 0:

        ratio = current_volume / previous

        if ratio >= tolerance:
            result = True

    st.session_state.volume_history[symbol] = current_volume

    return result


# ============================================================
# SCAN ONE STOCK
# ============================================================

def analyze_stock(symbol):

    intraday = get_history(
        symbol,
        Timespan.M1.name
    )

    if intraday is None or intraday.empty:
        return None

    latest = intraday.iloc[-1]

    price = float(latest["close"])

    # IMPORTANT:
    # Webull minute-bar volume may represent the volume
    # associated with the returned bar. We therefore use
    # cumulative intraday volume where available.

    current_volume = float(
        intraday["volume"].sum()
    )

    rvol = calculate_rvol(
        symbol,
        intraday
    )

    change = calculate_change(
        symbol,
        price
    )

    dollar_volume = (
        price * current_volume
    )

    repeat = calculate_repeat_volume(
        symbol,
        current_volume,
        st.session_state.settings[
            "repeat_tolerance"
        ]
    )

    return {
        "Time": datetime.now(NY).strftime(
            "%H:%M:%S"
        ),
        "Symbol": symbol,
        "Price": price,
        "Change %": change,
        "RVOL": rvol,
        "Volume": int(current_volume),
        "Dollar Volume": dollar_volume,
        "Repeat": repeat
    }


# ============================================================
# REGULAR SCAN
# ============================================================

def run_regular_scan():

    settings = st.session_state.settings

    rows = []

    symbols = DEFAULT_SYMBOLS.copy()

    for symbol in symbols:

        try:

            result = analyze_stock(symbol)

            if result is None:
                continue

            if result["Price"] < settings["min_price"]:
                continue

            if result["Price"] > settings["max_price"]:
                continue

            if result["Volume"] < settings["min_volume"]:
                continue

            if result["RVOL"] < settings["min_rvol"]:
                continue

            if result["Change %"] < settings["min_change"]:
                continue

            if (
                result["Dollar Volume"]
                < settings["min_dollar_volume"]
            ):
                continue

            rows.append(result)

        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df = df.sort_values(
        ["RVOL", "Change %"],
        ascending=False
    )

    return df.reset_index(drop=True)


# ============================================================
# WATCHLIST SCAN
# ============================================================

def run_watchlist_scan():

    rows = []

    for symbol in st.session_state.watchlist:

        try:

            result = analyze_stock(symbol)

            if result is None:
                continue

            rows.append(result)

        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df = df.sort_values(
        ["Repeat", "RVOL"],
        ascending=False
    )

    return df.reset_index(drop=True)


# ============================================================
# TRADINGVIEW CHART
# ============================================================

def show_chart(symbol):

    interval = st.session_state.settings[
        "chart_interval"
    ]

    if not symbol:
        symbol = "AAPL"

    chart_url = (
        "https://www.tradingview.com/widgetembed/"
        "?frameElementId=tradingview_chart"
        f"&symbol={symbol}"
        "&interval=" + str(interval) +
        "&hidetoptoolbar=0"
        "&symboledit=1"
        "&saveimage=0"
        "&toolbarbg=f1f3f6"
        "&studies=[]"
        "&theme=dark"
        "&style=1"
        "&timezone=America%2FNew_York"
        "&withdateranges=1"
        "&hideideas=1"
        "&hide_side_toolbar=0"
    )

    st.components.v1.iframe(
        chart_url,
        height=700,
        scrolling=False
    )


# ============================================================
# STOCK BUTTONS
# ============================================================

def stock_button(symbol):

    if st.button(
        symbol,
        key=f"stock_{symbol}",
        use_container_width=True
    ):

        st.session_state.selected_symbol = symbol
        st.rerun()


# ============================================================
# FILTER PANEL
# ============================================================

def filters():

    s = st.session_state.settings

    st.markdown(
        '<div class="tab-note">Scanner filters</div>',
        unsafe_allow_html=True
    )

    s["min_price"] = st.number_input(
        "Minimum price",
        min_value=0.0,
        value=float(s["min_price"]),
        step=0.10
    )

    s["max_price"] = st.number_input(
        "Maximum price",
        min_value=0.0,
        value=float(s["max_price"]),
        step=1.0
    )

    s["min_volume"] = st.number_input(
        "Minimum volume",
        min_value=0,
        value=int(s["min_volume"]),
        step=10000
    )

    s["min_rvol"] = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=float(s["min_rvol"]),
        step=0.1
    )

    s["min_change"] = st.number_input(
        "Minimum % change",
        min_value=-100.0,
        value=float(s["min_change"]),
        step=0.1
    )

    s["min_dollar_volume"] = st.number_input(
        "Minimum dollar volume",
        min_value=0,
        value=int(s["min_dollar_volume"]),
        step=100000
    )

    s["repeat_tolerance"] = st.slider(
        "Repeat volume tolerance",
        min_value=0.50,
        max_value=1.50,
        value=float(s["repeat_tolerance"]),
        step=0.01
    )

    s["refresh_seconds"] = st.number_input(
        "Refresh seconds",
        min_value=5,
        max_value=3600,
        value=int(s["refresh_seconds"]),
        step=5
    )

    s["chart_interval"] = st.selectbox(
        "Chart timeframe",
        ["1", "3", "5", "15", "30", "60"],
        index=[
            "1", "3", "5", "15", "30", "60"
        ].index(
            str(s["chart_interval"])
        )
    )

    s["auto_scan"] = st.checkbox(
        "Auto scan",
        value=bool(s["auto_scan"])
    )

    if st.button(
        "Save Filters",
        use_container_width=True
    ):

        save_json(
            SETTINGS_FILE,
            s
        )

        st.success("Saved")


# ============================================================
# WATCHLIST TAB
# ============================================================

def watchlist_tab():

    st.markdown(
        "### WATCHLIST"
    )

    st.caption(
        "Add stocks here. They will be used by "
        "WATCHLIST STOCK SCAN."
    )

    add_symbol = st.text_input(
        "Add symbol",
        placeholder="Example: NVDA"
    )

    if st.button(
        "Add to Watchlist",
        use_container_width=True
    ):

        symbol = add_symbol.strip().upper()

        if symbol:

            if symbol not in st.session_state.watchlist:

                st.session_state.watchlist.append(
                    symbol
                )

                save_json(
                    WATCHLIST_FILE,
                    st.session_state.watchlist
                )

                st.session_state.selected_symbol = symbol

                st.rerun()

    st.divider()

    if not st.session_state.watchlist:

        st.info(
            "Your watchlist is empty."
        )

        return

    for symbol in st.session_state.watchlist:

        c1, c2 = st.columns(
            [3, 1],
            gap="small"
        )

        with c1:

            if st.button(
                symbol,
                key=f"wl_{symbol}",
                use_container_width=True
            ):

                st.session_state.selected_symbol = symbol
                st.rerun()

        with c2:

            if st.button(
                "×",
                key=f"remove_{symbol}"
            ):

                st.session_state.watchlist.remove(
                    symbol
                )

                save_json(
                    WATCHLIST_FILE,
                    st.session_state.watchlist
                )

                st.rerun()


# ============================================================
# REGULAR SCAN TAB
# ============================================================

def regular_scan_tab():

    st.markdown(
        "### REGULAR SCAN"
    )

    filters()

    st.divider()

    if st.button(
        "SCAN NOW",
        use_container_width=True
    ):

        with st.spinner(
            "Scanning US stocks..."
        ):

            st.session_state.regular_results = (
                run_regular_scan()
            )

            st.session_state.last_scan_time = (
                datetime.now(NY)
            )

    df = st.session_state.regular_results

    if df.empty:

        st.info(
            "No results yet. Press SCAN NOW."
        )

        return

    st.caption(
        f"{len(df)} stocks found"
    )

    for _, row in df.iterrows():

        symbol = row["Symbol"]

        c1, c2, c3 = st.columns(
            [1.7, 1.1, 1.0],
            gap="small"
        )

        with c1:

            if st.button(
                symbol,
                key=f"regular_{symbol}",
                use_container_width=True
            ):

                st.session_state.selected_symbol = symbol
                st.rerun()

        with c2:

            change = row["Change %"]

            st.markdown(
                f"**{change:+.2f}%**"
            )

        with c3:

            st.markdown(
                f"RVOL **{row['RVOL']:.2f}**"
            )

        st.caption(
            f"Vol {row['Volume']:,}  |  "
            f"${row['Dollar Volume']:,.0f}"
        )


# ============================================================
# WATCHLIST STOCK SCAN TAB
# ============================================================

def watchlist_stock_scan_tab():

    st.markdown(
        "### WATCHLIST STOCK SCAN"
    )

    st.caption(
        "Only stocks in your Watchlist are scanned here."
    )

    if not st.session_state.watchlist:

        st.warning(
            "Add stocks to WATCHLIST first."
        )

        return

    if st.button(
        "SCAN WATCHLIST",
        use_container_width=True
    ):

        with st.spinner(
            "Scanning Watchlist..."
        ):

            st.session_state.watchlist_results = (
                run_watchlist_scan()
            )

    df = st.session_state.watchlist_results

    if df.empty:

        st.info(
            "No watchlist results yet."
        )

        return

    for _, row in df.iterrows():

        symbol = row["Symbol"]

        repeat = row["Repeat"]

        c1, c2, c3, c4 = st.columns(
            [1.4, 1.0, 1.0, 0.7],
            gap="small"
        )

        with c1:

            if st.button(
                symbol,
                key=f"watchscan_{symbol}",
                use_container_width=True
            ):

                st.session_state.selected_symbol = symbol
                st.rerun()

        with c2:

            st.markdown(
                f"{row['Change %']:+.2f}%"
            )

        with c3:

            st.markdown(
                f"RVOL {row['RVOL']:.2f}"
            )

        with c4:

            if repeat:

                st.markdown(
                    '<span class="green">■</span>',
                    unsafe_allow_html=True
                )

            else:

                st.markdown(
                    '<span style="color:#555">■</span>',
                    unsafe_allow_html=True
                )

        st.caption(
            f"Volume: {row['Volume']:,}"
        )


# ============================================================
# MAIN LAYOUT
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)

# ============================================================
# LEFT PANEL
# ============================================================

with left:

    st.markdown(
        '<div class="scanner-title">'
        'US STOCK SCANNER'
        '</div>',
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # THESE ARE THE THREE ACTUAL TOP TABS
    # --------------------------------------------------------

    tab1, tab2, tab3 = st.tabs(
        [
            "WATCHLIST",
            "REGULAR SCAN",
            "WATCHLIST STOCK SCAN"
        ]
    )

    with tab1:

        watchlist_tab()

    with tab2:

        regular_scan_tab()

    with tab3:

        watchlist_stock_scan_tab()


# ============================================================
# RIGHT PANEL
# ============================================================

with right:

    symbol = st.session_state.selected_symbol

    st.markdown(
        f"### {symbol}"
    )

    show_chart(symbol)


# ============================================================
# AUTO SCAN
# ============================================================

if st.session_state.settings["auto_scan"]:

    try:

        from streamlit_autorefresh import (
            st_autorefresh
        )

        st_autorefresh(
            interval=int(
                st.session_state.settings[
                    "refresh_seconds"
                ] * 1000
            ),
            key="scanner_refresh"
        )

    except ImportError:

        pass
