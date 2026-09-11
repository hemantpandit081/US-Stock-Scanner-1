import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="US Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# SETTINGS
# ============================================================

NY = ZoneInfo("America/New_York")

WATCHLIST_FILE = "watchlist.json"

DEFAULT_WATCHLIST = [
    "NVDA",
    "PLTR",
    "AMD"
]


# ============================================================
# WEBULL CONNECTION
# ============================================================

@st.cache_resource
def get_webull_client():

    app_key = st.secrets["WEBULL_APP_KEY"]
    app_secret = st.secrets["WEBULL_APP_SECRET"]

    endpoint = st.secrets.get(
        "WEBULL_ENDPOINT",
        "api.webull.com"
    )

    api_client = ApiClient(
        app_key,
        app_secret,
        "us"
    )

    api_client.add_endpoint(
        "us",
        endpoint
    )

    return DataClient(api_client)


try:

    webull = get_webull_client()

    WEBULL_CONNECTED = True
    WEBULL_ERROR = ""

except Exception as e:

    webull = None

    WEBULL_CONNECTED = False
    WEBULL_ERROR = str(e)


# ============================================================
# SESSION STATE
# ============================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "NVDA"

if "watchlist" not in st.session_state:
    st.session_state.watchlist = DEFAULT_WATCHLIST.copy()

if "regular_results" not in st.session_state:
    st.session_state.regular_results = []

if "watch_results" not in st.session_state:
    st.session_state.watch_results = []

if "last_regular_scan" not in st.session_state:
    st.session_state.last_regular_scan = None

if "last_watch_scan" not in st.session_state:
    st.session_state.last_watch_scan = None

if "scan_symbols" not in st.session_state:
    st.session_state.scan_symbols = []


# ============================================================
# WATCHLIST
# ============================================================

def load_watchlist():

    if not os.path.exists(WATCHLIST_FILE):
        return DEFAULT_WATCHLIST.copy()

    try:

        with open(
            WATCHLIST_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            return [
                str(x).upper().strip()
                for x in data
                if str(x).strip()
            ]

    except Exception:
        pass

    return DEFAULT_WATCHLIST.copy()


def save_watchlist():

    try:

        with open(
            WATCHLIST_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                st.session_state.watchlist,
                f,
                indent=2
            )

    except Exception:
        pass


if "watchlist_loaded" not in st.session_state:

    st.session_state.watchlist = load_watchlist()

    st.session_state.watchlist_loaded = True


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>

.block-container {
    padding-top: 0.4rem;
    padding-left: 0.6rem;
    padding-right: 0.6rem;
    max-width: 100%;
}

div[data-testid="stVerticalBlock"] {
    gap: 0.25rem;
}

.scanner-title {
    font-size: 21px;
    font-weight: 700;
    margin-bottom: 4px;
}

button[data-baseweb="tab"] {
    font-size: 10px !important;
    font-weight: 700 !important;
    padding-left: 5px !important;
    padding-right: 5px !important;
}

.green {
    color: #00c853;
    font-weight: 700;
}

.red {
    color: #ff5252;
    font-weight: 700;
}

.repeat {
    color: #00c853;
    font-size: 15px;
    font-weight: 800;
}

.small {
    font-size: 10px;
    color: #888;
}

</style>
""",
    unsafe_allow_html=True
)


# ============================================================
# GENERAL
# ============================================================

def select_stock(symbol):

    st.session_state.selected_symbol = (
        symbol.upper().strip()
    )


def add_to_watchlist(symbol):

    symbol = symbol.upper().strip()

    if (
        symbol
        and symbol not in st.session_state.watchlist
    ):

        st.session_state.watchlist.append(
            symbol
        )

        save_watchlist()


def remove_from_watchlist(symbol):

    if symbol in st.session_state.watchlist:

        st.session_state.watchlist.remove(
            symbol
        )

        save_watchlist()

    if (
        st.session_state.selected_symbol == symbol
        and st.session_state.watchlist
    ):

        st.session_state.selected_symbol = (
            st.session_state.watchlist[0]
        )


# ============================================================
# TRADINGVIEW
# ============================================================

def tradingview_chart(symbol):

    symbol = symbol.upper()

    url = (
        "https://www.tradingview.com/widgetembed/"
        f"?symbol=NASDAQ%3A{symbol}"
        "&interval=1"
        "&hidesidetoolbar=0"
        "&symboledit=1"
        "&saveimage=0"
        "&theme=dark"
        "&style=1"
        "&timezone=America%2FNew_York"
        "&withdateranges=1"
        "&hideideas=1"
    )

    html = f"""
    <iframe
        src="{url}"
        style="
            width:100%;
            height:720px;
            border:none;
        ">
    </iframe>
    """

    components.html(
        html,
        height=720,
        scrolling=False
    )


# ============================================================
# WEBULL HELPERS
# ============================================================

def response_json(response):

    if response is None:
        return None

    try:
        return response.json()

    except Exception:

        try:
            return response.json_data

        except Exception:
            return None


def number(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, str):
            value = value.replace(",", "")

        return float(value)

    except Exception:

        return default


# ============================================================
# WEBULL SNAPSHOT
# ============================================================

def get_snapshots(symbols):

    if not symbols:
        return []

    try:

        response = (
            webull.market_data
            .get_stock_snapshot(
                symbols,
                Category.US_STOCK.name
            )
        )

        if response.status_code != 200:
            return []

        data = response_json(response)

        if isinstance(data, dict):

            if "data" in data:
                data = data["data"]

            elif "items" in data:
                data = data["items"]

        if not isinstance(data, list):
            return []

        return data

    except Exception:

        return []


# ============================================================
# WEBULL HISTORICAL BARS
# ============================================================

def get_history(symbol):

    try:

        response = (
            webull.market_data
            .get_history_bar(
                symbol,
                Category.US_STOCK.name,
                Timespan.M1.name
            )
        )

        if response.status_code != 200:
            return pd.DataFrame()

        data = response_json(response)

        if isinstance(data, dict):

            if "data" in data:
                data = data["data"]

            elif "items" in data:
                data = data["items"]

        if not isinstance(data, list):
            return pd.DataFrame()

        return pd.DataFrame(data)

    except Exception:

        return pd.DataFrame()


# ============================================================
# BATCH HISTORICAL BARS
# ============================================================

def get_batch_history(symbols):

    if not symbols:
        return {}

    result = {}

    try:

        response = (
            webull.market_data
            .get_batch_history_bar(
                symbols,
                Category.US_STOCK.name,
                Timespan.M1.name,
                1200
            )
        )

        if response.status_code != 200:
            return result

        data = response_json(response)

        if isinstance(data, dict):

            if "data" in data:
                data = data["data"]

            elif "items" in data:
                data = data["items"]

        if isinstance(data, dict):

            for symbol, bars in data.items():

                if isinstance(bars, list):

                    result[symbol.upper()] = (
                        pd.DataFrame(bars)
                    )

        elif isinstance(data, list):

            for item in data:

                if not isinstance(item, dict):
                    continue

                symbol = (
                    item.get("symbol")
                    or item.get("ticker")
                )

                bars = (
                    item.get("bars")
                    or item.get("data")
                )

                if symbol and isinstance(bars, list):

                    result[
                        str(symbol).upper()
                    ] = pd.DataFrame(bars)

    except Exception:

        return {}

    return result


# ============================================================
# BAR NORMALISATION
# ============================================================

def normalise_bars(df):

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    rename = {}

    for column in df.columns:

        name = str(column).lower()

        if name in ["time", "timestamp", "trade_time"]:
            rename[column] = "time"

        elif name in ["open", "open_price"]:
            rename[column] = "open"

        elif name in ["high", "high_price"]:
            rename[column] = "high"

        elif name in ["low", "low_price"]:
            rename[column] = "low"

        elif name in ["close", "close_price"]:
            rename[column] = "close"

        elif name in ["volume", "vol"]:
            rename[column] = "volume"

    df = df.rename(columns=rename)

    required = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]

    for column in required:

        if column not in df.columns:
            df[column] = np.nan

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce"
        )

    if "time" in df.columns:

        try:

            df["time"] = pd.to_datetime(
                df["time"],
                unit="ms",
                errors="coerce"
            )

        except Exception:
            pass

    df = df.dropna(
        subset=["close", "volume"]
    )

    return df


# ============================================================
# REPEAT VOLUME
# ============================================================

def repeat_volume(
    bars,
    tolerance
):

    bars = normalise_bars(bars)

    if bars.empty:
        return False, 0.0

    volumes = (
        bars["volume"]
        .astype(float)
        .values
    )

    volumes = volumes[
        volumes > 0
    ]

    if len(volumes) < 3:
        return False, 0.0

    current = volumes[-1]

    previous = volumes[:-1]

    difference = np.abs(
        previous - current
    )

    nearest = previous[
        np.argmin(difference)
    ]

    if nearest <= 0:
        return False, 0.0

    ratio = current / nearest

    lower = tolerance
    upper = 1 / tolerance

    return (
        lower <= ratio <= upper,
        ratio
    )


# ============================================================
# RVOL
#
# Separate from repeat volume.
#
# This first implementation uses current cumulative
# volume against recent average daily volume.
# ============================================================

def calculate_rvol(
    current_volume,
    historical_volumes
):

    if current_volume <= 0:
        return 0.0

    if historical_volumes is None:
        return 0.0

    historical_volumes = [
        number(x)
        for x in historical_volumes
        if number(x) > 0
    ]

    if not historical_volumes:
        return 0.0

    average = np.mean(
        historical_volumes[-20:]
    )

    if average <= 0:
        return 0.0

    return (
        current_volume
        / average
    )


# ============================================================
# BUILD SNAPSHOT DICTIONARY
# ============================================================

def snapshot_dictionary(snapshots):

    result = {}

    for item in snapshots:

        if not isinstance(item, dict):
            continue

        symbol = (
            item.get("symbol")
            or item.get("ticker")
        )

        if not symbol:
            continue

        symbol = str(symbol).upper()

        result[symbol] = item

    return result


# ============================================================
# BUILD REGULAR RESULTS
# ============================================================

def build_regular_results(
    symbols,
    min_price,
    max_price,
    min_volume,
    min_change,
    min_rvol,
    min_dollar_volume,
    repeat_tolerance
):

    snapshots = get_snapshots(
        symbols
    )

    snapshot_map = snapshot_dictionary(
        snapshots
    )

    bars_map = get_batch_history(
        symbols
    )

    results = []

    for symbol in symbols:

        snapshot = snapshot_map.get(
            symbol,
            {}
        )

        price = number(
            snapshot.get("price")
            or snapshot.get("last_price")
        )

        change = number(
            snapshot.get("change_ratio")
            or snapshot.get("change")
        )

        # Webull change_ratio may be decimal.

        if abs(change) < 1:

            change *= 100

        volume = number(
            snapshot.get("volume")
        )

        if volume <= 0:

            bars = normalise_bars(
                bars_map.get(symbol)
            )

            if not bars.empty:

                volume = number(
                    bars["volume"].sum()
                )

        dollar_volume = (
            price * volume
        )

        if price < min_price:
            continue

        if price > max_price:
            continue

        if volume < min_volume:
            continue

        if change < min_change:
            continue

        if (
            dollar_volume
            < min_dollar_volume
        ):
            continue

        bars = normalise_bars(
            bars_map.get(symbol)
        )

        historical_volumes = []

        # Historical daily volume isn't retrieved
        # in this pass. We use prior intraday
        # sessions from returned bars where available.

        if not bars.empty:

            # Separate previous-session volumes
            # if timestamps are available.

            if "time" in bars.columns:

                try:

                    bars["date"] = (
                        pd.to_datetime(
                            bars["time"]
                        ).dt.date
                    )

                    dates = sorted(
                        bars["date"]
                        .dropna()
                        .unique()
                    )

                    if len(dates) > 1:

                        previous_dates = dates[:-1]

                        for d in previous_dates[-20:]:

                            day_volume = (
                                bars.loc[
                                    bars["date"] == d,
                                    "volume"
                                ].sum()
                            )

                            if day_volume > 0:

                                historical_volumes.append(
                                    day_volume
                                )

                except Exception:
                    pass

        rvol = calculate_rvol(
            volume,
            historical_volumes
        )

        repeat, ratio = repeat_volume(
            bars,
            repeat_tolerance
        )

        if rvol < min_rvol:
            continue

        results.append(
            {
                "symbol": symbol,
                "price": price,
                "change": change,
                "volume": volume,
                "dollar_volume": dollar_volume,
                "rvol": rvol,
                "repeat": repeat,
                "repeat_ratio": ratio
            }
        )

    results.sort(
        key=lambda x: (
            x["rvol"],
            x["change"],
            x["volume"]
        ),
        reverse=True
    )

    return results


# ============================================================
# WATCHLIST SCAN
# ============================================================

def build_watchlist_results(
    symbols,
    repeat_tolerance
):

    snapshots = get_snapshots(
        symbols
    )

    snapshot_map = snapshot_dictionary(
        snapshots
    )

    bars_map = get_batch_history(
        symbols
    )

    results = []

    for symbol in symbols:

        snapshot = snapshot_map.get(
            symbol,
            {}
        )

        price = number(
            snapshot.get("price")
        )

        change = number(
            snapshot.get("change_ratio")
            or snapshot.get("change")
        )

        if abs(change) < 1:
            change *= 100

        volume = number(
            snapshot.get("volume")
        )

        bars = normalise_bars(
            bars_map.get(symbol)
        )

        if volume <= 0 and not bars.empty:

            volume = number(
                bars["volume"].sum()
            )

        repeat, ratio = repeat_volume(
            bars,
            repeat_tolerance
        )

        results.append(
            {
                "symbol": symbol,
                "price": price,
                "change": change,
                "volume": volume,
                "repeat": repeat,
                "repeat_ratio": ratio
            }
        )

    results.sort(
        key=lambda x: (
            x["repeat"],
            x["volume"]
        ),
        reverse=True
    )

    return results


# ============================================================
# FORMAT
# ============================================================

def format_volume(value):

    value = number(value)

    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"

    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"

    if value >= 1_000:
        return f"{value / 1_000:.1f}K"

    return str(int(value))


# ============================================================
# MAIN LAYOUT
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT
# ============================================================

with left:

    st.markdown(
        '<div class="scanner-title">'
        'US STOCK SCANNER'
        '</div>',
        unsafe_allow_html=True
    )

    if WEBULL_CONNECTED:

        st.caption(
            "● Webull connected"
        )

    else:

        st.error(
            f"Webull connection failed: "
            f"{WEBULL_ERROR}"
        )

    (
        watchlist_tab,
        regular_tab,
        watchlist_scan_tab
    ) = st.tabs(
        [
            "WATCHLIST",
            "REGULAR SCAN",
            "WATCHLIST STOCK SCAN"
        ]
    )


    # ========================================================
    # WATCHLIST
    # ========================================================

    with watchlist_tab:

        st.markdown(
            "#### WATCHLIST"
        )

        new_symbol = st.text_input(
            "Add stock",
            placeholder="Enter symbol e.g. NVDA",
            label_visibility="collapsed"
        )

        if st.button(
            "＋ ADD STOCK",
            use_container_width=True
        ):

            add_to_watchlist(
                new_symbol
            )

            st.rerun()

        st.markdown("---")

        for symbol in st.session_state.watchlist:

            c1, c2 = st.columns(
                [5, 1]
            )

            with c1:

                if st.button(
                    symbol,
                    key=f"watch_{symbol}",
                    use_container_width=True
                ):

                    select_stock(symbol)

                    st.rerun()

            with c2:

                if st.button(
                    "×",
                    key=f"delete_{symbol}"
                ):

                    remove_from_watchlist(
                        symbol
                    )

                    st.rerun()


    # ========================================================
    # REGULAR SCAN
    # ========================================================

    with regular_tab:

        st.markdown(
            "#### REGULAR SCAN"
        )

        with st.expander(
            "⚙ FILTERS",
            expanded=False
        ):

            min_price = st.number_input(
                "Min Price",
                value=1.0,
                step=0.50
            )

            max_price = st.number_input(
                "Max Price",
                value=1000.0,
                step=10.0
            )

            min_volume = st.number_input(
                "Min Volume",
                value=100000,
                step=100000
            )

            min_rvol = st.number_input(
                "Min RVOL",
                value=1.5,
                step=0.1
            )

            min_change = st.number_input(
                "Min % Change",
                value=1.0,
                step=0.1
            )

            min_dollar_volume = st.number_input(
                "Min Dollar Volume",
                value=1_000_000,
                step=500_000
            )

            repeat_tolerance = st.slider(
                "Repeat Volume Tolerance",
                0.50,
                0.99,
                0.90,
                0.01
            )

            refresh_seconds = st.number_input(
                "Refresh Seconds",
                10,
                3600,
                60,
                10
            )

            max_symbols = st.number_input(
                "Symbols Per Scan",
                20,
                5000,
                500,
                50
            )

            auto_scan = st.checkbox(
                "Auto Scan",
                False
            )

        symbols_text = st.text_input(
            "US symbols",
            value="AAPL,NVDA,AMD,PLTR,TSLA,MSFT,AMZN,META,GOOGL,AVGO,COIN,HOOD,SOFI",
            label_visibility="collapsed"
        )

        symbols = [
            x.strip().upper()
            for x in symbols_text.split(",")
            if x.strip()
        ]

        symbols = list(
            dict.fromkeys(symbols)
        )

        symbols = symbols[
            :int(max_symbols)
        ]

        if st.button(
            "🔎 SCAN NOW",
            type="primary",
            use_container_width=True
        ):

            if not WEBULL_CONNECTED:

                st.error(
                    "Webull is not connected."
                )

            else:

                with st.spinner(
                    f"Scanning {len(symbols)} stocks..."
                ):

                    results = build_regular_results(
                        symbols,
                        min_price,
                        max_price,
                        min_volume,
                        min_change,
                        min_rvol,
                        min_dollar_volume,
                        repeat_tolerance
                    )

                st.session_state.regular_results = results

                st.session_state.last_regular_scan = (
                    datetime.now(NY).strftime(
                        "%H:%M:%S"
                    )
                )

                st.rerun()

        if auto_scan:

            if st.session_state.last_regular_scan:

                st.caption(
                    "Auto scan enabled — "
                    f"last scan "
                    f"{st.session_state.last_regular_scan}"
                )

        st.markdown("---")

        results = (
            st.session_state.regular_results
        )

        if not results:

            st.info(
                "No stocks found. "
                "Run SCAN NOW."
            )

        else:

            st.caption(
                f"{len(results)} stocks found | "
                f"Last scan "
                f"{st.session_state.last_regular_scan}"
            )

            h1, h2, h3, h4 = st.columns(
                [2, 1.2, 1.1, 0.8]
            )

            h1.markdown("**STOCK**")
            h2.markdown("**CHANGE**")
            h3.markdown("**RVOL**")
            h4.markdown("**REP**")

            for stock in results:

                symbol = stock["symbol"]

                c1, c2, c3, c4 = st.columns(
                    [2, 1.2, 1.1, 0.8]
                )

                with c1:

                    if st.button(
                        symbol,
                        key=f"regular_{symbol}",
                        use_container_width=True
                    ):

                        select_stock(symbol)

                        st.rerun()

                with c2:

                    change = stock["change"]

                    css = (
                        "green"
                        if change >= 0
                        else "red"
                    )

                    prefix = (
                        "+"
                        if change >= 0
                        else ""
                    )

                    st.markdown(
                        f'<span class="{css}">'
                        f'{prefix}{change:.2f}%'
                        f'</span>',
                        unsafe_allow_html=True
                    )

                with c3:

                    st.write(
                        f'{stock["rvol"]:.2f}x'
                    )

                with c4:

                    if stock["repeat"]:

                        st.markdown(
                            '<span class="repeat">'
                            '■'
                            '</span>',
                            unsafe_allow_html=True
                        )

                st.caption(
                    f'${stock["price"]:.2f} | '
                    f'Vol {format_volume(stock["volume"])} | '
                    f'$Vol '
                    f'{format_volume(stock["dollar_volume"])}'
                )


    # ========================================================
    # WATCHLIST STOCK SCAN
    # ========================================================

    with watchlist_scan_tab:

        st.markdown(
            "#### WATCHLIST STOCK SCAN"
        )

        st.caption(
            "Repeat-volume monitoring is separate "
            "from RVOL."
        )

        watch_tolerance = st.slider(
            "Repeat Tolerance",
            0.50,
            0.99,
            0.90,
            0.01
        )

        if st.button(
            "🔎 SCAN WATCHLIST",
            type="primary",
            use_container_width=True
        ):

            if not WEBULL_CONNECTED:

                st.error(
                    "Webull is not connected."
                )

            elif not st.session_state.watchlist:

                st.warning(
                    "Watchlist is empty."
                )

            else:

                with st.spinner(
                    "Scanning Watchlist..."
                ):

                    results = (
                        build_watchlist_results(
                            st.session_state.watchlist,
                            watch_tolerance
                        )
                    )

                st.session_state.watch_results = (
                    results
                )

                st.session_state.last_watch_scan = (
                    datetime.now(NY).strftime(
                        "%H:%M:%S"
                    )
                )

                st.rerun()

        st.markdown("---")

        results = (
            st.session_state.watch_results
        )

        if results:

            h1, h2, h3, h4 = st.columns(
                [2, 1.3, 1.1, 0.8]
            )

            h1.markdown("**STOCK**")
            h2.markdown("**VOLUME**")
            h3.markdown("**RVOL**")
            h4.markdown("**REP**")

            for stock in results:

                symbol = stock["symbol"]

                c1, c2, c3, c4 = st.columns(
                    [2, 1.3, 1.1, 0.8]
                )

                with c1:

                    if st.button(
                        symbol,
                        key=f"watchscan_{symbol}",
                        use_container_width=True
                    ):

                        select_stock(symbol)

                        st.rerun()

                with c2:

                    st.write(
                        format_volume(
                            stock["volume"]
                        )
                    )

                with c3:

                    st.write(
                        "-"
                    )

                with c4:

                    if stock["repeat"]:

                        st.markdown(
                            '<span class="repeat">'
                            '■'
                            '</span>',
                            unsafe_allow_html=True
                        )

                st.caption(
                    f'${stock["price"]:.2f} | '
                    f'{stock["change"]:.2f}%'
                )

        else:

            st.info(
                "Run SCAN WATCHLIST."
            )


# ============================================================
# RIGHT 65%
# ============================================================

with right:

    selected = (
        st.session_state.selected_symbol
    )

    st.markdown(
        f"### {selected}"
    )

    st.caption(
        "US Market • Webull data • TradingView chart"
    )

    tradingview_chart(
        selected
    )
