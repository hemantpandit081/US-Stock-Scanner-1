import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="US Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

NY_TZ = ZoneInfo("America/New_York")

WATCHLIST_FILE = "watchlist.json"

DEFAULT_WATCHLIST = [
    "NVDA",
    "PLTR",
    "AMD"
]

# Same height for left scanner and right TradingView
PANEL_HEIGHT = 900


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    /* -------------------------------------------------------
       PAGE
    ------------------------------------------------------- */

    .block-container {
        padding-top: 0.35rem;
        padding-bottom: 0rem;
        padding-left: 0.7rem;
        padding-right: 0.7rem;
    }

    /* Remove unnecessary spacing */
    div[data-testid="stVerticalBlock"] {
        gap: 0.25rem;
    }

    /* -------------------------------------------------------
       SCANNER TITLE
    ------------------------------------------------------- */

    .scanner-title {
        font-size: 22px;
        font-weight: 700;
        line-height: 1.1;
        margin: 0;
        padding: 0;
    }

    /* -------------------------------------------------------
       SMALL TEXT
    ------------------------------------------------------- */

    .small {
        font-size: 11px;
    }

    /* -------------------------------------------------------
       COLOURS
    ------------------------------------------------------- */

    .green {
        color: #00c853;
        font-weight: 700;
    }

    .red {
        color: #ff5252;
        font-weight: 700;
    }

    /* -------------------------------------------------------
       REPEAT MARKER
    ------------------------------------------------------- */

    .repeat {
        color: white;
        font-size: 16px;
        font-weight: 700;
        line-height: 1;
    }

    /* -------------------------------------------------------
       TABS
    ------------------------------------------------------- */

    button[data-baseweb="tab"] {
        font-size: 11px;
        font-weight: 700;
        padding-left: 7px;
        padding-right: 7px;
    }

    /* -------------------------------------------------------
       TRADINGVIEW
    ------------------------------------------------------- */

    iframe {
        border: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* -------------------------------------------------------
       BUTTONS
    ------------------------------------------------------- */

    button {
        font-size: 12px !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)


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

except Exception:

    webull = None
    WEBULL_CONNECTED = False


# ============================================================
# SESSION STATE
# ============================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "NVDA"

if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

if "regular_results" not in st.session_state:
    st.session_state.regular_results = pd.DataFrame()

if "watch_results" not in st.session_state:
    st.session_state.watch_results = pd.DataFrame()

if "last_regular_scan" not in st.session_state:
    st.session_state.last_regular_scan = None

if "last_watch_scan" not in st.session_state:
    st.session_state.last_watch_scan = None


# ============================================================
# WATCHLIST
# ============================================================

def load_watchlist():

    if not os.path.exists(WATCHLIST_FILE):
        return DEFAULT_WATCHLIST.copy()

    try:

        with open(WATCHLIST_FILE, "r") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return DEFAULT_WATCHLIST.copy()


def save_watchlist():

    try:

        with open(WATCHLIST_FILE, "w") as f:

            json.dump(
                st.session_state.watchlist,
                f,
                indent=2
            )

    except Exception:
        pass


if not st.session_state.watchlist:

    st.session_state.watchlist = (
        load_watchlist()
    )


# ============================================================
# STOCK SELECTION
# ============================================================

def select_stock(symbol):

    symbol = str(
        symbol
    ).upper().strip()

    if symbol:

        st.session_state.selected_symbol = (
            symbol
        )


def add_to_watchlist(symbol):

    symbol = str(
        symbol
    ).upper().strip()

    if not symbol:
        return

    if symbol not in st.session_state.watchlist:

        st.session_state.watchlist.append(
            symbol
        )

        save_watchlist()


def remove_from_watchlist(symbol):

    symbol = str(
        symbol
    ).upper().strip()

    if symbol in st.session_state.watchlist:

        st.session_state.watchlist.remove(
            symbol
        )

        save_watchlist()


# ============================================================
# TRADINGVIEW CHART
# ============================================================

def tradingview_chart(symbol):

    symbol = str(
        symbol
    ).upper().strip()

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
    <html>
    <head>

    <style>

        html,
        body {{
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
            overflow: hidden;
            background: #131722;
        }}

        iframe {{
            width: 100%;
            height: 100%;
            border: 0;
            margin: 0;
            padding: 0;
            display: block;
        }}

    </style>

    </head>

    <body>

        <iframe
            src="{url}"
            allowtransparency="true"
            frameborder="0"
            scrolling="no">
        </iframe>

    </body>
    </html>
    """

    components.html(
        html,
        height=PANEL_HEIGHT,
        scrolling=False
    )


# ============================================================
# WEBULL HELPERS
# ============================================================

def safe_float(value, default=0.0):

    try:

        if value is None:
            return default

        if isinstance(value, str):

            value = value.replace(
                ",",
                ""
            )

        return float(value)

    except Exception:

        return default


def get_value(
    obj,
    names,
    default=None
):

    if obj is None:
        return default

    for name in names:

        try:

            if isinstance(obj, dict):

                if name in obj:
                    return obj[name]

            else:

                if hasattr(obj, name):
                    return getattr(
                        obj,
                        name
                    )

        except Exception:
            pass

    return default


# ============================================================
# SNAPSHOTS
# ============================================================

def get_snapshots(symbols):

    if not webull or not symbols:
        return {}

    try:

        result = (
            webull.market_data
            .get_stock_snapshot(
                symbols,
                Category.US_STOCK.name
            )
        )

        if result is None:
            return {}

        if isinstance(result, dict):

            if "data" in result:
                result = result["data"]

            if isinstance(result, dict):
                return result

        snapshots = {}

        if isinstance(result, list):

            for item in result:

                symbol = get_value(
                    item,
                    [
                        "symbol",
                        "ticker",
                        "stockSymbol"
                    ]
                )

                if symbol:

                    snapshots[
                        str(symbol).upper()
                    ] = item

        return snapshots

    except Exception:

        return {}


# ============================================================
# HISTORY
# ============================================================

def get_history(symbol):

    if not webull:
        return pd.DataFrame()

    try:

        result = (
            webull.market_data
            .get_history_bar(
                symbol,
                Category.US_STOCK.name,
                Timespan.M1.name
            )
        )

        if result is None:
            return pd.DataFrame()

        if isinstance(result, dict):

            result = result.get(
                "data",
                result
            )

        if isinstance(result, list):

            return normalise_bars(
                pd.DataFrame(result)
            )

        if isinstance(result, pd.DataFrame):

            return normalise_bars(
                result
            )

    except Exception:

        pass

    return pd.DataFrame()


# ============================================================
# BATCH HISTORY
# ============================================================

def get_batch_history(symbols):

    if not webull or not symbols:
        return {}

    try:

        result = (
            webull.market_data
            .get_batch_history_bar(
                symbols,
                Category.US_STOCK.name,
                Timespan.M1.name,
                1200
            )
        )

        if result is None:
            return {}

        if isinstance(result, dict):

            result = result.get(
                "data",
                result
            )

        histories = {}

        if isinstance(result, dict):

            for symbol, data in result.items():

                try:

                    df = pd.DataFrame(
                        data
                    )

                    histories[
                        str(symbol).upper()
                    ] = normalise_bars(
                        df
                    )

                except Exception:

                    pass

        elif isinstance(result, list):

            for item in result:

                symbol = get_value(
                    item,
                    [
                        "symbol",
                        "ticker"
                    ]
                )

                if not symbol:
                    continue

                try:

                    df = pd.DataFrame(
                        item.get(
                            "bars",
                            item.get(
                                "data",
                                []
                            )
                        )
                    )

                    histories[
                        str(symbol).upper()
                    ] = normalise_bars(
                        df
                    )

                except Exception:

                    pass

        return histories

    except Exception:

        return {}


# ============================================================
# NORMALISE BARS
# ============================================================

def normalise_bars(df):

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    rename_map = {}

    for col in df.columns:

        c = str(
            col
        ).lower()

        if c in [
            "time",
            "timestamp",
            "datetime",
            "t"
        ]:

            rename_map[col] = "time"

        elif c in [
            "open",
            "o"
        ]:

            rename_map[col] = "open"

        elif c in [
            "high",
            "h"
        ]:

            rename_map[col] = "high"

        elif c in [
            "low",
            "l"
        ]:

            rename_map[col] = "low"

        elif c in [
            "close",
            "c",
            "price"
        ]:

            rename_map[col] = "close"

        elif c in [
            "volume",
            "v",
            "vol"
        ]:

            rename_map[col] = "volume"

    df = df.rename(
        columns=rename_map
    )

    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]:

        if col in df.columns:

            df[col] = pd.to_numeric(
                df[col],
                errors="coerce"
            )

    if "time" in df.columns:

        try:

            if pd.api.types.is_numeric_dtype(
                df["time"]
            ):

                df["time"] = pd.to_datetime(
                    df["time"],
                    unit="ms",
                    errors="coerce"
                )

            else:

                df["time"] = pd.to_datetime(
                    df["time"],
                    errors="coerce"
                )

        except Exception:

            pass

    required = []

    if "time" in df.columns:
        required.append("time")

    if "volume" in df.columns:
        required.append("volume")

    if required:

        df = df.dropna(
            subset=required
        )

    if "time" in df.columns:

        df = df.sort_values(
            "time"
        )

    return df.reset_index(
        drop=True
    )


# ============================================================
# REPEAT VOLUME
# ============================================================

def repeat_volume(
    bars,
    tolerance=0.90
):

    if bars is None or bars.empty:
        return False

    if "volume" not in bars.columns:
        return False

    volumes = (
        pd.to_numeric(
            bars["volume"],
            errors="coerce"
        )
        .dropna()
        .tolist()
    )

    if len(volumes) < 2:
        return False

    current_volume = volumes[-1]

    previous_volumes = volumes[:-1]

    if not previous_volumes:
        return False

    for previous_volume in previous_volumes[-20:]:

        if previous_volume <= 0:
            continue

        ratio = (
            current_volume /
            previous_volume
        )

        if ratio >= tolerance:

            return True

    return False


# ============================================================
# RVOL
# ============================================================

def calculate_rvol(
    current_volume,
    historical_volumes
):

    current_volume = safe_float(
        current_volume
    )

    if current_volume <= 0:
        return 0.0

    historical = []

    for value in historical_volumes:

        value = safe_float(
            value
        )

        if value > 0:
            historical.append(
                value
            )

    if not historical:
        return 0.0

    average_volume = np.mean(
        historical
    )

    if average_volume <= 0:
        return 0.0

    return (
        current_volume /
        average_volume
    )


# ============================================================
# DAILY VOLUME
# ============================================================

def get_daily_volumes(bars):

    if bars is None or bars.empty:
        return []

    if "time" not in bars.columns:
        return []

    if "volume" not in bars.columns:
        return []

    temp = bars.copy()

    temp["date"] = (
        temp["time"].dt.date
    )

    daily = (
        temp
        .groupby("date")["volume"]
        .sum()
        .sort_index()
    )

    return daily.tolist()


# ============================================================
# REGULAR SCAN
# ============================================================

def build_regular_results(
    symbols,
    min_price,
    max_price,
    min_volume,
    min_rvol,
    min_change,
    min_dollar_volume,
    repeat_tolerance
):

    symbols = [
        str(s).upper().strip()
        for s in symbols
        if str(s).strip()
    ]

    symbols = list(
        dict.fromkeys(
            symbols
        )
    )

    if not symbols:
        return pd.DataFrame()

    snapshots = get_snapshots(
        symbols
    )

    histories = get_batch_history(
        symbols
    )

    rows = []

    for symbol in symbols:

        snapshot = snapshots.get(
            symbol
        )

        if snapshot is None:
            continue

        price = safe_float(
            get_value(
                snapshot,
                [
                    "lastPrice",
                    "last",
                    "price",
                    "close"
                ]
            )
        )

        change = safe_float(
            get_value(
                snapshot,
                [
                    "changePercent",
                    "changePct",
                    "percentChange",
                    "pctChange"
                ]
            )
        )

        volume = safe_float(
            get_value(
                snapshot,
                [
                    "volume",
                    "totalVolume",
                    "vol"
                ]
            )
        )

        name = get_value(
            snapshot,
            [
                "name",
                "securityName"
            ],
            symbol
        )

        dollar_volume = (
            price * volume
        )

        bars = histories.get(
            symbol,
            pd.DataFrame()
        )

        daily_volumes = (
            get_daily_volumes(
                bars
            )
        )

        if len(daily_volumes) >= 2:

            historical_volumes = (
                daily_volumes[-11:-1]
            )

        else:

            historical_volumes = (
                daily_volumes[:-1]
            )

        rvol = calculate_rvol(
            volume,
            historical_volumes
        )

        repeat = repeat_volume(
            bars,
            repeat_tolerance
        )

        # ----------------------------------------------------
        # FILTERS
        # ----------------------------------------------------

        if price < min_price:
            continue

        if price > max_price:
            continue

        if volume < min_volume:
            continue

        if rvol < min_rvol:
            continue

        if change < min_change:
            continue

        if dollar_volume < min_dollar_volume:
            continue

        rows.append(
            {
                "Time": datetime.now(
                    NY_TZ
                ).strftime("%H:%M:%S"),

                "Symbol": symbol,

                "Name": name,

                "Price": price,

                "% Change": change,

                "RVOL": rvol,

                "Volume": volume,

                "$ Volume": dollar_volume,

                "Repeat": repeat
            }
        )

    if not rows:

        return pd.DataFrame(
            columns=[
                "Time",
                "Symbol",
                "Name",
                "Price",
                "% Change",
                "RVOL",
                "Volume",
                "$ Volume",
                "Repeat"
            ]
        )

    df = pd.DataFrame(
        rows
    )

    df = df.sort_values(
        [
            "RVOL",
            "% Change"
        ],
        ascending=[
            False,
            False
        ]
    )

    return df.reset_index(
        drop=True
    )


# ============================================================
# WATCHLIST SCAN
# ============================================================

def build_watchlist_results(
    symbols,
    repeat_tolerance
):

    if not symbols:
        return pd.DataFrame()

    snapshots = get_snapshots(
        symbols
    )

    histories = get_batch_history(
        symbols
    )

    rows = []

    for symbol in symbols:

        snapshot = snapshots.get(
            symbol
        )

        if snapshot is None:
            continue

        price = safe_float(
            get_value(
                snapshot,
                [
                    "lastPrice",
                    "last",
                    "price",
                    "close"
                ]
            )
        )

        change = safe_float(
            get_value(
                snapshot,
                [
                    "changePercent",
                    "changePct",
                    "percentChange",
                    "pctChange"
                ]
            )
        )

        volume = safe_float(
            get_value(
                snapshot,
                [
                    "volume",
                    "totalVolume",
                    "vol"
                ]
            )
        )

        bars = histories.get(
            symbol,
            pd.DataFrame()
        )

        daily_volumes = (
            get_daily_volumes(
                bars
            )
        )

        if len(daily_volumes) >= 2:

            historical_volumes = (
                daily_volumes[-11:-1]
            )

        else:

            historical_volumes = (
                daily_volumes[:-1]
            )

        rvol = calculate_rvol(
            volume,
            historical_volumes
        )

        repeat = repeat_volume(
            bars,
            repeat_tolerance
        )

        rows.append(
            {
                "Time": datetime.now(
                    NY_TZ
                ).strftime("%H:%M:%S"),

                "Symbol": symbol,

                "Price": price,

                "% Change": change,

                "Volume": volume,

                "RVOL": rvol,

                "Repeat": repeat
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        rows
    )

    df = df.sort_values(
        "RVOL",
        ascending=False
    )

    return df.reset_index(
        drop=True
    )


# ============================================================
# FORMAT VOLUME
# ============================================================

def format_volume(value):

    value = safe_float(
        value
    )

    if value >= 1_000_000_000:

        return (
            f"{value / 1_000_000_000:.2f}B"
        )

    if value >= 1_000_000:

        return (
            f"{value / 1_000_000:.2f}M"
        )

    if value >= 1_000:

        return (
            f"{value / 1_000:.1f}K"
        )

    return f"{value:,.0f}"


# ============================================================
# MAIN 35 / 65 LAYOUT
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT SCANNER
# ============================================================

with left:

    st.markdown(
        '<div class="scanner-title">'
        'US STOCK SCANNER'
        '</div>',
        unsafe_allow_html=True
    )

    if WEBULL_CONNECTED:

        st.markdown(
            '<span class="green">'
            '● Webull connected'
            '</span>',
            unsafe_allow_html=True
        )

    else:

        st.error(
            "Webull connection failed."
        )

    # --------------------------------------------------------
    # THREE TABS
    # --------------------------------------------------------

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
            "### Watchlist"
        )

        col1, col2 = st.columns(
            [3, 1]
        )

        with col1:

            new_symbol = st.text_input(
                "Add stock",
                placeholder="AAPL",
                label_visibility="collapsed"
            )

        with col2:

            if st.button(
                "ADD",
                use_container_width=True
            ):

                if new_symbol.strip():

                    add_to_watchlist(
                        new_symbol
                    )

                    st.rerun()

        st.markdown("---")

        if st.session_state.watchlist:

            for symbol in (
                st.session_state.watchlist
            ):

                col1, col2 = st.columns(
                    [4, 1]
                )

                with col1:

                    if st.button(
                        symbol,
                        key=f"watch_{symbol}",
                        use_container_width=True
                    ):

                        select_stock(
                            symbol
                        )

                with col2:

                    if st.button(
                        "×",
                        key=f"remove_{symbol}"
                    ):

                        remove_from_watchlist(
                            symbol
                        )

                        st.rerun()

        else:

            st.info(
                "Watchlist is empty."
            )


    # ========================================================
    # REGULAR SCAN
    # ========================================================

    with regular_tab:

        st.markdown(
            "### Regular Scan"
        )

        with st.expander(
            "Scanner Filters",
            expanded=False
        ):

            c1, c2 = st.columns(2)

            with c1:

                min_price = st.number_input(
                    "Minimum Price",
                    min_value=0.0,
                    value=1.0,
                    step=0.50
                )

                min_volume = st.number_input(
                    "Minimum Volume",
                    min_value=0,
                    value=100000,
                    step=10000
                )

                min_rvol = st.number_input(
                    "Minimum RVOL",
                    min_value=0.0,
                    value=1.5,
                    step=0.1
                )

                min_change = st.number_input(
                    "Minimum % Change",
                    min_value=-100.0,
                    value=1.0,
                    step=0.5
                )

            with c2:

                max_price = st.number_input(
                    "Maximum Price",
                    min_value=0.0,
                    value=1000.0,
                    step=10.0
                )

                min_dollar_volume = st.number_input(
                    "Minimum $ Volume",
                    min_value=0,
                    value=1_000_000,
                    step=100000
                )

                repeat_tolerance = st.number_input(
                    "Repeat Tolerance",
                    min_value=0.1,
                    max_value=2.0,
                    value=0.90,
                    step=0.05
                )

                refresh_seconds = st.number_input(
                    "Refresh Seconds",
                    min_value=1,
                    value=60,
                    step=1
                )

            max_symbols = st.number_input(
                "Maximum Symbols",
                min_value=1,
                value=500,
                step=50
            )

            auto_scan = st.checkbox(
                "Auto Scan",
                value=False
            )

            symbols_text = st.text_area(
                "US Stock Symbols",
                value=(
                    "AAPL,NVDA,AMD,PLTR,TSLA,"
                    "MSFT,AMZN,META,GOOGL,AVGO,"
                    "COIN,HOOD,SOFI"
                ),
                height=80
            )

        symbols = [
            x.strip().upper()
            for x in symbols_text.split(",")
            if x.strip()
        ]

        symbols = symbols[
            :int(max_symbols)
        ]

        if st.button(
            "SCAN NOW",
            type="primary",
            use_container_width=True
        ):

            with st.spinner(
                "Scanning US stocks..."
            ):

                st.session_state.regular_results = (
                    build_regular_results(
                        symbols,
                        min_price,
                        max_price,
                        min_volume,
                        min_rvol,
                        min_change,
                        min_dollar_volume,
                        repeat_tolerance
                    )
                )

                st.session_state.last_regular_scan = (
                    datetime.now(
                        NY_TZ
                    ).strftime("%H:%M:%S")
                )

        if st.session_state.last_regular_scan:

            st.caption(
                "Last scan: "
                + str(
                    st.session_state.last_regular_scan
                )
            )

        results = (
            st.session_state.regular_results
        )

        # ----------------------------------------------------
        # HEADERS
        # ----------------------------------------------------

        h1, h2, h3, h4 = st.columns(
            [3, 2, 2, 1]
        )

        with h1:
            st.markdown("**STOCK**")

        with h2:
            st.markdown("**%**")

        with h3:
            st.markdown("**RVOL**")

        with h4:
            st.markdown("**REP**")

        # ----------------------------------------------------
        # RESULTS
        # ----------------------------------------------------

        if (
            results is not None
            and not results.empty
        ):

            for _, row in results.iterrows():

                symbol = row["Symbol"]

                c1, c2, c3, c4 = st.columns(
                    [3, 2, 2, 1]
                )

                with c1:

                    if st.button(
                        symbol,
                        key=f"regular_{symbol}",
                        use_container_width=True
                    ):

                        select_stock(
                            symbol
                        )

                with c2:

                    change = safe_float(
                        row["% Change"]
                    )

                    if change >= 0:

                        st.markdown(
                            f'<span class="green">'
                            f'+{change:.2f}%'
                            f'</span>',
                            unsafe_allow_html=True
                        )

                    else:

                        st.markdown(
                            f'<span class="red">'
                            f'{change:.2f}%'
                            f'</span>',
                            unsafe_allow_html=True
                        )

                with c3:

                    rvol = safe_float(
                        row["RVOL"]
                    )

                    if rvol >= 3:

                        st.markdown(
                            f"**{rvol:.2f}x**"
                        )

                    else:

                        st.write(
                            f"{rvol:.2f}x"
                        )

                with c4:

                    if row["Repeat"]:

                        st.markdown(
                            '<span class="repeat">'
                            '■'
                            '</span>',
                            unsafe_allow_html=True
                        )

        else:

            st.info(
                "Run a scan to show stocks."
            )


    # ========================================================
    # WATCHLIST STOCK SCAN
    # ========================================================

    with watchlist_scan_tab:

        st.markdown(
            "### Watchlist Stock Scan"
        )

        repeat_tolerance_watch = st.number_input(
            "Repeat Volume Tolerance",
            min_value=0.1,
            max_value=2.0,
            value=0.90,
            step=0.05,
            key="watch_repeat_tolerance"
        )

        if st.button(
            "SCAN WATCHLIST",
            type="primary",
            use_container_width=True
        ):

            with st.spinner(
                "Scanning watchlist..."
            ):

                st.session_state.watch_results = (
                    build_watchlist_results(
                        st.session_state.watchlist,
                        repeat_tolerance_watch
                    )
                )

                st.session_state.last_watch_scan = (
                    datetime.now(
                        NY_TZ
                    ).strftime("%H:%M:%S")
                )

        if st.session_state.last_watch_scan:

            st.caption(
                "Last scan: "
                + str(
                    st.session_state.last_watch_scan
                )
            )

        # ----------------------------------------------------
        # HEADERS
        # ----------------------------------------------------

        h1, h2, h3, h4 = st.columns(
            [3, 2, 2, 1]
        )

        with h1:
            st.markdown("**STOCK**")

        with h2:
            st.markdown("**VOLUME**")

        with h3:
            st.markdown("**RVOL**")

        with h4:
            st.markdown("**REP**")

        watch_results = (
            st.session_state.watch_results
        )

        if (
            watch_results is not None
            and not watch_results.empty
        ):

            for _, row in watch_results.iterrows():

                symbol = row["Symbol"]

                c1, c2, c3, c4 = st.columns(
                    [3, 2, 2, 1]
                )

                with c1:

                    if st.button(
                        symbol,
                        key=f"watchscan_{symbol}",
                        use_container_width=True
                    ):

                        select_stock(
                            symbol
                        )

                with c2:

                    st.write(
                        format_volume(
                            row["Volume"]
                        )
                    )

                with c3:

                    st.write(
                        f"{safe_float(row['RVOL']):.2f}x"
                    )

                with c4:

                    if row["Repeat"]:

                        st.markdown(
                            '<span class="repeat">'
                            '■'
                            '</span>',
                            unsafe_allow_html=True
                        )

        else:

            st.info(
                "Run watchlist scan to show stocks."
            )


# ============================================================
# RIGHT SIDE
# TRADINGVIEW SAME HEIGHT AS SCANNER
# ============================================================

with right:

    selected = (
        st.session_state.selected_symbol
    )

    # No heading above chart.
    # This keeps the chart top aligned with
    # the scanner title on the left.

    tradingview_chart(
        selected
    )
