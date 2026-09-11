import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# =========================================================
# WEBULL SDK
# =========================================================

try:
    from webull.core.client import ApiClient
    from webull.data.common.category import Category
    from webull.data.common.timespan import Timespan
    from webull.data.data_client import DataClient
except ImportError:
    ApiClient = None
    Category = None
    Timespan = None
    DataClient = None


# =========================================================
# PAGE
# =========================================================

st.set_page_config(
    page_title="US Webull Momentum Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================================================
# CSS
# =========================================================

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 0.45rem;
        padding-left: 0.55rem;
        padding-right: 0.55rem;
        padding-bottom: 0.2rem;
    }

    div[data-testid="column"] {
        padding-left: 3px;
        padding-right: 3px;
    }

    .scanner-title {
        font-size: 22px;
        font-weight: 700;
        margin-bottom: 2px;
    }

    .small-text {
        font-size: 11px;
    }

    .tab-active {
        font-weight: 700;
    }

    button {
        font-size: 12px !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# CONSTANTS
# =========================================================

NY = ZoneInfo("America/New_York")

SETTINGS_FILE = "scanner_settings.json"


# =========================================================
# INITIAL STOCK UNIVERSE
#
# This is the starter universe.
# Later we can replace this with the complete Webull
# instrument universe.
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
    "RIVN",
]


# =========================================================
# DEFAULT SETTINGS
# =========================================================

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
    "chart_interval": "1",
}


# =========================================================
# SETTINGS FUNCTIONS
# =========================================================

def load_settings():

    if os.path.exists(SETTINGS_FILE):

        try:

            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)

            result = DEFAULT_SETTINGS.copy()
            result.update(saved)

            return result

        except Exception:
            pass

    return DEFAULT_SETTINGS.copy()


def save_settings():

    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)


settings = load_settings()


# =========================================================
# SESSION STATE
# =========================================================

if "active_tab" not in st.session_state:
    st.session_state.active_tab = "REGULAR SCAN"

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "NVDA"

if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

if "regular_results" not in st.session_state:
    st.session_state.regular_results = pd.DataFrame()

if "watchlist_results" not in st.session_state:
    st.session_state.watchlist_results = pd.DataFrame()

if "watchlist_scan_results" not in st.session_state:
    st.session_state.watchlist_scan_results = pd.DataFrame()

if "volume_history" not in st.session_state:
    st.session_state.volume_history = {}

if "last_scan" not in st.session_state:
    st.session_state.last_scan = None

if "webull_error" not in st.session_state:
    st.session_state.webull_error = ""


# =========================================================
# WEBULL CONNECTION
# =========================================================

def get_secret(name, default=""):

    try:

        if name in st.secrets:
            return st.secrets[name]

    except Exception:
        pass

    return os.getenv(name, default)


WEBULL_APP_KEY = get_secret("WEBULL_APP_KEY")
WEBULL_APP_SECRET = get_secret("WEBULL_APP_SECRET")


@st.cache_resource
def create_webull_client():

    if ApiClient is None:
        raise RuntimeError(
            "Webull SDK is not installed. "
            "Run: pip install --upgrade webull-openapi-python-sdk"
        )

    if not WEBULL_APP_KEY or not WEBULL_APP_SECRET:

        raise RuntimeError(
            "Webull credentials not found. "
            "Set WEBULL_APP_KEY and WEBULL_APP_SECRET."
        )

    api_client = ApiClient(
        WEBULL_APP_KEY,
        WEBULL_APP_SECRET,
        "us",
    )

    # Production
    api_client.add_endpoint(
        "us",
        "api.webull.com",
    )

    data_client = DataClient(api_client)

    return data_client


# =========================================================
# WEBULL CONNECTION STATUS
# =========================================================

def get_webull():

    try:

        return create_webull_client()

    except Exception as e:

        st.session_state.webull_error = str(e)

        return None


# =========================================================
# MARKET STATUS
# =========================================================

def market_open():

    now = datetime.now(NY)

    if now.weekday() >= 5:
        return False

    minutes = (
        now.hour * 60
        + now.minute
    )

    return 570 <= minutes <= 960


# =========================================================
# NUMBER HELPERS
# =========================================================

def number(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", "")

        return float(value)

    except Exception:

        return default


# =========================================================
# FORMATTERS
# =========================================================

def fmt_volume(value):

    value = number(value)

    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"

    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"

    if value >= 1_000:
        return f"{value / 1_000:.0f}K"

    return f"{value:.0f}"


def fmt_money(value):

    value = number(value)

    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"

    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"

    if value >= 1_000:
        return f"${value / 1_000:.0f}K"

    return f"${value:.0f}"


# =========================================================
# PARSE WEBULL RESPONSE
# =========================================================

def response_json(response):

    try:

        if response is None:
            return None

        if hasattr(response, "json"):

            return response.json()

        return response

    except Exception:

        return None


# =========================================================
# EXTRACT LIST FROM RESPONSE
# =========================================================

def extract_items(data):

    if data is None:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        for key in [
            "data",
            "items",
            "list",
            "results",
            "stocks",
            "bars",
        ]:

            value = data.get(key)

            if isinstance(value, list):
                return value

        # Some Webull responses may be keyed by symbol

        for key in [
            "symbols",
            "snapshot",
            "snapshots",
        ]:

            value = data.get(key)

            if isinstance(value, list):
                return value

    return []


# =========================================================
# WEBULL SNAPSHOT
# =========================================================

def get_snapshots(symbols):

    if not symbols:
        return []

    client = get_webull()

    if client is None:
        return []

    try:

        # The current Webull SDK exposes market-data methods.
        #
        # We try the batch/snapshot methods supported by
        # the installed SDK version.

        method = getattr(
            client.market_data,
            "get_batch_snapshot",
            None,
        )

        if method is None:

            method = getattr(
                client.market_data,
                "get_snapshot",
                None,
            )

        if method is None:

            raise RuntimeError(
                "Installed Webull SDK does not expose "
                "the expected snapshot method."
            )

        response = method(
            symbols,
            Category.US_STOCK.name,
        )

        data = response_json(response)

        return extract_items(data)

    except Exception as e:

        st.session_state.webull_error = (
            f"Snapshot error: {e}"
        )

        return []


# =========================================================
# WEBULL BATCH MINUTE BARS
# =========================================================

def get_batch_minute_bars(symbols, count=390):

    if not symbols:
        return {}

    client = get_webull()

    if client is None:
        return {}

    try:

        response = client.market_data.get_batch_history_bar(
            symbols,
            Category.US_STOCK.name,
            Timespan.M1.name,
            count,
        )

        data = response_json(response)

        return data if data is not None else {}

    except Exception as e:

        st.session_state.webull_error = (
            f"Minute-bar error: {e}"
        )

        return {}


# =========================================================
# NORMALIZE SNAPSHOT
# =========================================================

def normalize_snapshot(item):

    if not isinstance(item, dict):
        return None

    symbol = (
        item.get("symbol")
        or item.get("ticker")
        or item.get("sec_symbol")
    )

    if not symbol:
        return None

    price = number(
        item.get("price")
        or item.get("latest_price")
        or item.get("last_price")
    )

    volume = number(
        item.get("volume")
        or item.get("trade_volume")
    )

    change_ratio = number(
        item.get("change_ratio")
        or item.get("change_percent")
    )

    # Webull may return change ratio as decimal.
    if abs(change_ratio) < 1:

        change_pct = change_ratio * 100

    else:

        change_pct = change_ratio

    pre_close = number(
        item.get("pre_close")
        or item.get("previous_close")
    )

    return {
        "Symbol": str(symbol).upper(),
        "Price": price,
        "Volume": volume,
        "Change": change_pct,
        "PreClose": pre_close,
    }


# =========================================================
# BUILD SNAPSHOT DATAFRAME
# =========================================================

def build_snapshot_df(symbols):

    raw = get_snapshots(symbols)

    rows = []

    for item in raw:

        row = normalize_snapshot(item)

        if row is not None:

            rows.append(row)

    if not rows:

        return pd.DataFrame()

    df = pd.DataFrame(rows)

    return df


# =========================================================
# GET DAILY BASELINE VOLUME
# =========================================================
#
# For speed, we use historical bars only where needed.
# This avoids making one request for every symbol.
# =========================================================

def calculate_rvol_from_bars(symbol, bars):

    try:

        if bars is None:
            return 0

        if isinstance(bars, dict):

            bars = extract_items(bars)

        if not isinstance(bars, list):
            return 0

        if len(bars) < 10:
            return 0

        volumes = []

        for bar in bars:

            if not isinstance(bar, dict):
                continue

            volume = number(
                bar.get("volume")
                or bar.get("trade_volume")
            )

            if volume > 0:
                volumes.append(volume)

        if len(volumes) < 10:
            return 0

        current = volumes[-1]

        previous = volumes[:-1]

        average = (
            sum(previous[-20:])
            / len(previous[-20:])
        )

        if average <= 0:
            return 0

        return current / average

    except Exception:

        return 0


# =========================================================
# VOLUME HISTORY
# =========================================================

def add_volume_history(symbol, volume):

    if volume <= 0:
        return

    history = st.session_state.volume_history.get(
        symbol,
        [],
    )

    history.append(
        float(volume)
    )

    if len(history) > 30:

        history = history[-30:]

    st.session_state.volume_history[
        symbol
    ] = history


# =========================================================
# REPEAT VOLUME
# =========================================================

def repeat_signal(symbol, current_volume):

    history = st.session_state.volume_history.get(
        symbol,
        [],
    )

    if not history:

        return False, 0, 0

    tolerance = float(
        settings["repeat_tolerance"]
    )

    best_previous = 0
    best_ratio = 0

    for previous in history:

        if previous <= 0:
            continue

        ratio = (
            current_volume
            / previous
        )

        if ratio >= tolerance:

            if ratio > best_ratio:

                best_ratio = ratio
                best_previous = previous

    return (
        best_previous > 0,
        best_previous,
        best_ratio,
    )


# =========================================================
# PREPARE MARKET DATA
# =========================================================

def prepare_market_data(symbols):

    if not symbols:
        return pd.DataFrame()

    snapshots = build_snapshot_df(symbols)

    if snapshots.empty:
        return pd.DataFrame()

    # -----------------------------------------------------
    # Use minute bars for each symbol in a single batch
    # where available.
    # -----------------------------------------------------

    bars_data = get_batch_minute_bars(
        symbols,
        count=100,
    )

    results = []

    for _, row in snapshots.iterrows():

        symbol = row["Symbol"]

        price = number(
            row["Price"]
        )

        volume = number(
            row["Volume"]
        )

        change = number(
            row["Change"]
        )

        dollar_volume = (
            price * volume
        )

        # -------------------------------------------------
        # Find bars for this symbol
        # -------------------------------------------------

        symbol_bars = None

        if isinstance(bars_data, dict):

            symbol_bars = (
                bars_data.get(symbol)
                or bars_data.get(
                    symbol.upper()
                )
            )

        # -------------------------------------------------
        # RVOL
        # -------------------------------------------------

        rvol = calculate_rvol_from_bars(
            symbol,
            symbol_bars,
        )

        # -------------------------------------------------
        # REPEAT
        # -------------------------------------------------

        repeat, previous_volume, repeat_ratio = (
            repeat_signal(
                symbol,
                volume,
            )
        )

        results.append(
            {
                "Symbol": symbol,
                "Price": price,
                "Change": change,
                "RVOL": rvol,
                "Volume": volume,
                "Dollar": dollar_volume,
                "Repeat": repeat,
                "PreviousVolume": previous_volume,
                "RepeatRatio": repeat_ratio,
            }
        )

    if not results:

        return pd.DataFrame()

    return pd.DataFrame(results)


# =========================================================
# FILTER REGULAR SCAN
# =========================================================

def apply_regular_filters(df):

    if df.empty:
        return df

    result = df.copy()

    result = result[
        (result["Price"] >= settings["min_price"])
        &
        (result["Price"] <= settings["max_price"])
        &
        (result["Volume"] >= settings["min_volume"])
        &
        (result["RVOL"] >= settings["min_rvol"])
        &
        (result["Change"] >= settings["min_change"])
        &
        (
            result["Dollar"]
            >= settings["min_dollar_volume"]
        )
    ]

    result = result.sort_values(
        [
            "Repeat",
            "RVOL",
            "Change",
        ],
        ascending=[
            False,
            False,
            False,
        ],
    )

    return result.reset_index(drop=True)


# =========================================================
# REGULAR SCAN
# =========================================================

def run_regular_scan():

    df = prepare_market_data(
        STOCKS
    )

    if df.empty:
        return df

    # Store volume after calculating repeat.
    for _, row in df.iterrows():

        add_volume_history(
            row["Symbol"],
            row["Volume"],
        )

    return apply_regular_filters(df)


# =========================================================
# WATCHLIST SCAN
# =========================================================

def run_watchlist_scan():

    symbols = list(
        st.session_state.watchlist
    )

    if not symbols:

        return pd.DataFrame()

    df = prepare_market_data(
        symbols
    )

    if df.empty:
        return df

    # IMPORTANT:
    # Do NOT apply the Regular Scan filters here.
    #
    # Watchlist Stock Scan scans the stocks selected
    # by the user, even if they no longer satisfy
    # Regular Scan filters.

    df = df.sort_values(
        [
            "Repeat",
            "RepeatRatio",
            "RVOL",
            "Change",
        ],
        ascending=[
            False,
            False,
            False,
            False,
        ],
    )

    # Store volume AFTER comparison
    for _, row in df.iterrows():

        add_volume_history(
            row["Symbol"],
            row["Volume"],
        )

    return df.reset_index(drop=True)


# =========================================================
# WATCHLIST DATA
# =========================================================

def refresh_watchlist_data():

    symbols = list(
        st.session_state.watchlist
    )

    if not symbols:

        return pd.DataFrame()

    df = prepare_market_data(
        symbols
    )

    return df.reset_index(drop=True)


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown("## ⚙️ Scanner Filters")

    settings["min_price"] = st.number_input(
        "Minimum Price",
        min_value=0.0,
        value=float(
            settings["min_price"]
        ),
        step=0.50,
    )

    settings["max_price"] = st.number_input(
        "Maximum Price",
        min_value=0.0,
        value=float(
            settings["max_price"]
        ),
        step=10.0,
    )

    settings["min_volume"] = st.number_input(
        "Minimum Volume",
        min_value=0,
        value=int(
            settings["min_volume"]
        ),
        step=10000,
    )

    settings["min_rvol"] = st.number_input(
        "Minimum RVOL",
        min_value=0.0,
        value=float(
            settings["min_rvol"]
        ),
        step=0.1,
    )

    settings["min_change"] = st.number_input(
        "Minimum % Change",
        value=float(
            settings["min_change"]
        ),
        step=0.5,
    )

    settings["min_dollar_volume"] = st.number_input(
        "Minimum Dollar Volume",
        min_value=0,
        value=int(
            settings["min_dollar_volume"]
        ),
        step=100000,
    )

    st.markdown("### Repeat Volume")

    settings["repeat_tolerance"] = st.slider(
        "Repeat tolerance",
        min_value=0.50,
        max_value=1.00,
        value=float(
            settings["repeat_tolerance"]
        ),
        step=0.01,
    )

    settings["refresh_seconds"] = st.number_input(
        "Refresh seconds",
        min_value=10,
        max_value=3600,
        value=int(
            settings["refresh_seconds"]
        ),
        step=10,
    )

    settings["chart_interval"] = st.selectbox(
        "TradingView interval",
        [
            "1",
            "5",
            "15",
            "30",
            "60",
            "D",
        ],
        index=[
            "1",
            "5",
            "15",
            "30",
            "60",
            "D",
        ].index(
            settings["chart_interval"]
        ),
    )

    settings["auto_scan"] = st.checkbox(
        "Auto scan",
        value=bool(
            settings["auto_scan"]
        ),
    )

    if st.button(
        "💾 Save Filters",
        use_container_width=True,
    ):

        save_settings()

        st.success("Filters saved")


# =========================================================
# HEADER
# =========================================================

h1, h2, h3 = st.columns(
    [6, 2, 2]
)

with h1:

    st.markdown(
        '<div class="scanner-title">'
        '📈 US Webull Momentum Scanner'
        '</div>',
        unsafe_allow_html=True,
    )

with h2:

    if market_open():

        st.success("🟢 US MARKET OPEN")

    else:

        st.info("⚪ MARKET CLOSED")

with h3:

    if st.button(
        "🔄 SCAN NOW",
        use_container_width=True,
    ):

        if (
            st.session_state.active_tab
            == "REGULAR SCAN"
        ):

            st.session_state.regular_results = (
                run_regular_scan()
            )

        elif (
            st.session_state.active_tab
            == "WATCHLIST"
        ):

            st.session_state.watchlist_results = (
                refresh_watchlist_data()
            )

        else:

            st.session_state.watchlist_scan_results = (
                run_watchlist_scan()
            )

        st.session_state.last_scan = datetime.now(
            NY
        ).strftime("%H:%M:%S")


# =========================================================
# WEBULL ERROR
# =========================================================

if st.session_state.webull_error:

    st.warning(
        "Webull: "
        + st.session_state.webull_error
    )


# =========================================================
# FIRST SCAN
# =========================================================

if (
    st.session_state.regular_results.empty
    and not st.session_state.webull_error
):

    st.session_state.regular_results = (
        run_regular_scan()
    )


# =========================================================
# MAIN 35 / 65
# =========================================================

left, right = st.columns(
    [35, 65],
    gap="small",
)


# =========================================================
# LEFT PANEL
# =========================================================

with left:

    # =====================================================
    # EXACT THREE TOP TABS
    # =====================================================

    tab1, tab2, tab3 = st.columns(
        [1, 1, 1]
    )

    # -----------------------------------------------------
    # WATCHLIST
    # -----------------------------------------------------

    with tab1:

        if st.button(
            "WATCHLIST",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.active_tab
                == "WATCHLIST"
                else "secondary"
            ),
        ):

            st.session_state.active_tab = (
                "WATCHLIST"
            )

            st.rerun()


    # -----------------------------------------------------
    # REGULAR SCAN
    # -----------------------------------------------------

    with tab2:

        if st.button(
            "REGULAR SCAN",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.active_tab
                == "REGULAR SCAN"
                else "secondary"
            ),
        ):

            st.session_state.active_tab = (
                "REGULAR SCAN"
            )

            st.rerun()


    # -----------------------------------------------------
    # WATCHLIST STOCK SCAN
    # -----------------------------------------------------

    with tab3:

        if st.button(
            "WATCHLIST STOCK SCAN",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.active_tab
                == "WATCHLIST STOCK SCAN"
                else "secondary"
            ),
        ):

            st.session_state.active_tab = (
                "WATCHLIST STOCK SCAN"
            )

            if st.session_state.watchlist:

                st.session_state.watchlist_scan_results = (
                    run_watchlist_scan()
                )

            st.rerun()


    st.markdown("---")


    # =====================================================
    # WATCHLIST TAB
    # =====================================================

    if st.session_state.active_tab == "WATCHLIST":

        st.markdown(
            f"### ⭐ Watchlist "
            f"({len(st.session_state.watchlist)})"
        )

        if not st.session_state.watchlist:

            st.info(
                "Your Watchlist is empty."
            )

            st.caption(
                "Go to REGULAR SCAN and press + "
                "next to a stock."
            )

        else:

            # ---------------------------------------------
            # COLUMN HEADINGS
            # ---------------------------------------------

            a, b, c, d, e = st.columns(
                [0.45, 1.5, 1, 0.9, 0.9]
            )

            a.caption("")
            b.caption("SYMBOL")
            c.caption("PRICE")
            d.caption("%")
            e.caption("RVOL")


            # ---------------------------------------------
            # GET CURRENT DATA
            # ---------------------------------------------

            if (
                st.session_state.watchlist_results.empty
            ):

                watch_df = refresh_watchlist_data()

                st.session_state.watchlist_results = (
                    watch_df
                )

            else:

                watch_df = (
                    st.session_state.watchlist_results
                )


            # ---------------------------------------------
            # ROWS
            # ---------------------------------------------

            for symbol in st.session_state.watchlist:

                match = pd.DataFrame()

                if (
                    not watch_df.empty
                    and "Symbol" in watch_df.columns
                ):

                    match = watch_df[
                        watch_df["Symbol"]
                        == symbol
                    ]


                c0, c1, c2, c3, c4 = st.columns(
                    [0.45, 1.5, 1, 0.9, 0.9]
                )


                # -----------------------------------------
                # REMOVE
                # -----------------------------------------

                with c0:

                    if st.button(
                        "×",
                        key=f"remove_{symbol}",
                    ):

                        st.session_state.watchlist.remove(
                            symbol
                        )

                        st.session_state.watchlist_results = (
                            pd.DataFrame()
                        )

                        st.rerun()


                # -----------------------------------------
                # SYMBOL
                # -----------------------------------------

                with c1:

                    label = symbol

                    if (
                        not match.empty
                        and bool(
                            match.iloc[0]["Repeat"]
                        )
                    ):

                        label = "■ " + symbol

                    if st.button(
                        label,
                        key=f"watch_{symbol}",
                        use_container_width=True,
                    ):

                        st.session_state.selected_symbol = (
                            symbol
                        )

                        st.rerun()


                # -----------------------------------------
                # DATA
                # -----------------------------------------

                if not match.empty:

                    row = match.iloc[0]

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

                else:

                    with c2:
                        st.caption("--")

                    with c3:
                        st.caption("--")

                    with c4:
                        st.caption("--")


    # =====================================================
    # REGULAR SCAN TAB
    # =====================================================

    elif st.session_state.active_tab == "REGULAR SCAN":

        st.markdown(
            "### 🔎 Regular Scan"
        )

        df = st.session_state.regular_results

        if df.empty:

            st.info(
                "No stocks currently match "
                "your filters."
            )

        else:

            # ---------------------------------------------
            # HEADER
            # ---------------------------------------------

            a, b, c, d, e, f = st.columns(
                [0.5, 1.45, 0.9, 0.8, 0.8, 1.0]
            )

            a.caption("WL")
            b.caption("SYMBOL")
            c.caption("PRICE")
            d.caption("%")
            e.caption("RVOL")
            f.caption("$VOL")


            # ---------------------------------------------
            # ROWS
            # ---------------------------------------------

            for _, row in df.iterrows():

                symbol = row["Symbol"]

                c0, c1, c2, c3, c4, c5 = st.columns(
                    [0.5, 1.45, 0.9, 0.8, 0.8, 1.0]
                )


                # -----------------------------------------
                # WATCHLIST ADD BUTTON
                # -----------------------------------------

                with c0:

                    in_watchlist = (
                        symbol
                        in st.session_state.watchlist
                    )

                    button = (
                        "★"
                        if in_watchlist
                        else "+"
                    )

                    if st.button(
                        button,
                        key=f"add_{symbol}",
                        help=(
                            "Remove from Watchlist"
                            if in_watchlist
                            else "Add to Watchlist"
                        ),
                    ):

                        if in_watchlist:

                            st.session_state.watchlist.remove(
                                symbol
                            )

                        else:

                            st.session_state.watchlist.append(
                                symbol
                            )

                        st.session_state.watchlist_results = (
                            pd.DataFrame()
                        )

                        st.rerun()


                # -----------------------------------------
                # SYMBOL
                # -----------------------------------------

                with c1:

                    if bool(row["Repeat"]):

                        symbol_label = (
                            "■ " + symbol
                        )

                    else:

                        symbol_label = symbol

                    if st.button(
                        symbol_label,
                        key=f"regular_{symbol}",
                        use_container_width=True,
                    ):

                        st.session_state.selected_symbol = (
                            symbol
                        )

                        st.rerun()


                # -----------------------------------------
                # PRICE
                # -----------------------------------------

                with c2:

                    st.caption(
                        f"${row['Price']:.2f}"
                    )


                # -----------------------------------------
                # CHANGE
                # -----------------------------------------

                with c3:

                    st.caption(
                        f"{row['Change']:.1f}%"
                    )


                # -----------------------------------------
                # RVOL
                # -----------------------------------------

                with c4:

                    st.caption(
                        f"{row['RVOL']:.1f}x"
                    )


                # -----------------------------------------
                # DOLLAR VOLUME
                # -----------------------------------------

                with c5:

                    st.caption(
                        fmt_money(
                            row["Dollar"]
                        )
                    )


    # =====================================================
    # WATCHLIST STOCK SCAN TAB
    # =====================================================

    else:

        st.markdown(
            "### 🔁 Watchlist Stock Scan"
        )

        st.caption(
            "Only stocks saved in your Watchlist "
            "are scanned here."
        )


        # ---------------------------------------------
        # WATCHLIST EMPTY
        # ---------------------------------------------

        if not st.session_state.watchlist:

            st.info(
                "Watchlist is empty."
            )

            st.caption(
                "Add stocks from REGULAR SCAN first."
            )


        else:

            # ---------------------------------------------
            # SCAN BUTTON
            # ---------------------------------------------

            if st.button(
                "🔄 SCAN WATCHLIST NOW",
                use_container_width=True,
            ):

                st.session_state.watchlist_scan_results = (
                    run_watchlist_scan()
                )

                st.rerun()


            df = (
                st.session_state.watchlist_scan_results
            )


            if df.empty:

                st.info(
                    "Press SCAN WATCHLIST NOW."
                )

            else:

                # -----------------------------------------
                # HEADERS
                # -----------------------------------------

                a, b, c, d, e, f = st.columns(
                    [1.3, 0.9, 0.8, 0.8, 0.9, 1.0]
                )

                a.caption("SYMBOL")
                b.caption("PRICE")
                c.caption("%")
                d.caption("RVOL")
                e.caption("VOLUME")
                f.caption("REPEAT")


                # -----------------------------------------
                # ROWS
                # -----------------------------------------

                for _, row in df.iterrows():

                    symbol = row["Symbol"]

                    c1, c2, c3, c4, c5, c6 = st.columns(
                        [1.3, 0.9, 0.8, 0.8, 0.9, 1.0]
                    )


                    # -------------------------------------
                    # SYMBOL
                    # -------------------------------------

                    with c1:

                        if bool(row["Repeat"]):

                            label = (
                                "■ " + symbol
                            )

                        else:

                            label = symbol

                        if st.button(
                            label,
                            key=f"scanwl_{symbol}",
                            use_container_width=True,
                        ):

                            st.session_state.selected_symbol = (
                                symbol
                            )

                            st.rerun()


                    # -------------------------------------
                    # PRICE
                    # -------------------------------------

                    with c2:

                        st.caption(
                            f"${row['Price']:.2f}"
                        )


                    # -------------------------------------
                    # CHANGE
                    # -------------------------------------

                    with c3:

                        st.caption(
                            f"{row['Change']:.1f}%"
                        )


                    # -------------------------------------
                    # RVOL
                    # -------------------------------------

                    with c4:

                        st.caption(
                            f"{row['RVOL']:.1f}x"
                        )


                    # -------------------------------------
                    # VOLUME
                    # -------------------------------------

                    with c5:

                        st.caption(
                            fmt_volume(
                                row["Volume"]
                            )
                        )


                    # -------------------------------------
                    # REPEAT
                    # -------------------------------------

                    with c6:

                        if bool(row["Repeat"]):

                            st.markdown(
                                "■ **YES**"
                            )

                        else:

                            st.caption("—")


# =========================================================
# RIGHT PANEL - TRADINGVIEW
# =========================================================

with right:

    symbol = (
        st.session_state.selected_symbol
    )

    interval = (
        settings["chart_interval"]
    )


    st.markdown(
        f"### 📊 {symbol}"
    )


    # -----------------------------------------------------
    # TRADINGVIEW URL
    # -----------------------------------------------------

    tv_symbol = (
        f"NASDAQ:{symbol}"
    )

    tradingview_url = (
        "https://www.tradingview.com/widgetembed/"
        "?frameElementId=tradingview_chart"
        f"&symbol={tv_symbol.replace(':', '%3A')}"
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


    # -----------------------------------------------------
    # TRADINGVIEW
    # -----------------------------------------------------

    html = f"""
    <iframe
        id="tradingview_chart"
        src="{tradingview_url}"
        style="
            width:100%;
            height:720px;
            border:0;
        "
        allowtransparency="true"
        frameborder="0"
        scrolling="no">
    </iframe>
    """


    components.html(
        html,
        height=735,
        scrolling=False,
    )


# =========================================================
# STATUS
# =========================================================

if st.session_state.last_scan:

    st.caption(
        f"Last scan: "
        f"{st.session_state.last_scan} "
        f"New York time"
    )


# =========================================================
# AUTO REFRESH
# =========================================================

if settings["auto_scan"]:

    refresh = int(
        settings["refresh_seconds"]
    )

    st.markdown(
        f"""
        <script>

        setTimeout(function() {{

            window.parent.location.reload();

        }}, {refresh * 1000});

        </script>
        """,
        unsafe_allow_html=True,
    )
