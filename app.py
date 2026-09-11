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

# EXACT SAME HEIGHT FOR BOTH PANELS
PANEL_HEIGHT = 900


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    /* ======================================================
       PAGE
       ====================================================== */

    .block-container {
        padding-top: 0.20rem !important;
        padding-bottom: 0rem !important;
        padding-left: 0.55rem !important;
        padding-right: 0.55rem !important;
        max-width: 100% !important;
    }

    div[data-testid="stVerticalBlock"] {
        gap: 0.20rem;
    }

    /* ======================================================
       SCANNER PANEL
       ====================================================== */

    .scanner-panel {
        height: 900px;
        overflow-y: auto;
        overflow-x: hidden;
        padding-right: 5px;
    }

    .scanner-panel::-webkit-scrollbar {
        width: 6px;
    }

    .scanner-panel::-webkit-scrollbar-thumb {
        background: #555;
        border-radius: 4px;
    }

    /* ======================================================
       TITLE
       ====================================================== */

    .scanner-title {
        font-size: 22px;
        font-weight: 700;
        line-height: 1.05;
        margin: 0 0 2px 0;
        padding: 0;
    }

    .connection {
        font-size: 10px;
        line-height: 1;
        margin-bottom: 3px;
    }

    /* ======================================================
       SMALL TEXT
       ====================================================== */

    .small {
        font-size: 10px;
    }

    /* ======================================================
       COLOURS
       ====================================================== */

    .green {
        color: #00c853;
        font-weight: 700;
    }

    .red {
        color: #ff5252;
        font-weight: 700;
    }

    .yellow {
        color: #ffd600;
        font-weight: 700;
    }

    /* ======================================================
       REPEAT
       ====================================================== */

    .repeat {
        color: white;
        font-size: 15px;
        font-weight: 800;
        line-height: 1;
        text-align: center;
    }

    /* ======================================================
       TABLE HEADER
       ====================================================== */

    .sort-header {
        font-size: 9px;
        font-weight: 700;
        color: #aaaaaa;
        white-space: nowrap;
        text-align: center;
        padding-top: 2px;
        padding-bottom: 2px;
    }

    /* ======================================================
       ROW TEXT
       ====================================================== */

    .row-text {
        font-size: 10px;
        line-height: 1.1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* ======================================================
       TABS
       ====================================================== */

    button[data-baseweb="tab"] {
        font-size: 10px !important;
        font-weight: 700 !important;
        padding-left: 5px !important;
        padding-right: 5px !important;
    }

    /* ======================================================
       BUTTONS
       ====================================================== */

    button {
        font-size: 10px !important;
    }

    /* Smaller row buttons */
    div.stButton > button {
        min-height: 25px !important;
        height: 25px !important;
        padding-top: 0px !important;
        padding-bottom: 0px !important;
        padding-left: 3px !important;
        padding-right: 3px !important;
    }

    /* ======================================================
       TRADINGVIEW
       ====================================================== */

    iframe {
        border: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    /* ======================================================
       INPUTS
       ====================================================== */

    div[data-baseweb="input"] input {
        font-size: 11px !important;
    }

    div[data-baseweb="select"] {
        font-size: 11px !important;
    }

    /* ======================================================
       EXPANDER
       ====================================================== */

    div[data-testid="stExpander"] {
        border: 1px solid rgba(128,128,128,0.25);
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

    app_secret = st.secrets[
        "WEBULL_APP_SECRET"
    ]

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

DEFAULT_STATE = {
    "selected_symbol": "NVDA",
    "watchlist": [],
    "regular_results": pd.DataFrame(),
    "watch_results": pd.DataFrame(),
    "last_regular_scan": None,
    "last_watch_scan": None,

    # SORTING
    "regular_sort_column": "RVOL",
    "regular_sort_ascending": False,

    "watch_sort_column": "RVOL",
    "watch_sort_ascending": False,
}

for key, value in DEFAULT_STATE.items():

    if key not in st.session_state:

        st.session_state[key] = value


# ============================================================
# WATCHLIST
# ============================================================

def load_watchlist():

    if not os.path.exists(
        WATCHLIST_FILE
    ):

        return DEFAULT_WATCHLIST.copy()

    try:

        with open(
            WATCHLIST_FILE,
            "r"
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
            "w"
        ) as f:

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

        st.session_state.selected_symbol = symbol


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
# TRADINGVIEW
# ============================================================

def tradingview_chart(symbol):

    symbol = str(
        symbol
    ).upper().strip()

    if not symbol:

        symbol = "NVDA"

    # Default US routing.
    # TradingView can still allow symbol editing.
    tradingview_symbol = (
        f"NASDAQ:{symbol}"
    )

    url = (
        "https://www.tradingview.com/widgetembed/"
        f"?symbol={tradingview_symbol.replace(':', '%3A')}"
        "&interval=1"
        "&hidesidetoolbar=0"
        "&symboledit=1"
        "&saveimage=0"
        "&theme=dark"
        "&style=1"
        "&timezone=America%2FNew_York"
        "&withdateranges=1"
        "&hideideas=1"
        "&studies=[]"
        "&hidelegend=0"
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

def safe_float(
    value,
    default=0.0
):

    try:

        if value is None:

            return default

        if isinstance(
            value,
            str
        ):

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

            if isinstance(
                obj,
                dict
            ):

                if name in obj:

                    return obj[name]

            else:

                if hasattr(
                    obj,
                    name
                ):

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

    if (
        not webull
        or not symbols
    ):

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

        if isinstance(
            result,
            dict
        ):

            if "data" in result:

                result = result["data"]

            if isinstance(
                result,
                dict
            ):

                # Sometimes one symbol can
                # be returned as a dictionary.
                if any(
                    key in result
                    for key in [
                        "symbol",
                        "ticker",
                        "lastPrice",
                        "price"
                    ]
                ):

                    symbol = get_value(
                        result,
                        [
                            "symbol",
                            "ticker",
                            "stockSymbol"
                        ]
                    )

                    if symbol:

                        return {
                            str(symbol).upper(): result
                        }

                return result

        snapshots = {}

        if isinstance(
            result,
            list
        ):

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

        if isinstance(
            result,
            dict
        ):

            result = result.get(
                "data",
                result
            )

        if isinstance(
            result,
            list
        ):

            return normalise_bars(
                pd.DataFrame(result)
            )

        if isinstance(
            result,
            pd.DataFrame
        ):

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

    if (
        not webull
        or not symbols
    ):

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

        if isinstance(
            result,
            dict
        ):

            result = result.get(
                "data",
                result
            )

        histories = {}

        if isinstance(
            result,
            dict
        ):

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

        elif isinstance(
            result,
            list
        ):

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

                    if isinstance(
                        item,
                        dict
                    ):

                        raw_data = item.get(
                            "bars",
                            item.get(
                                "data",
                                []
                            )
                        )

                    else:

                        raw_data = []

                    df = pd.DataFrame(
                        raw_data
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

    if (
        df is None
        or df.empty
    ):

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

        required.append(
            "time"
        )

    if "volume" in df.columns:

        required.append(
            "volume"
        )

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

    if (
        bars is None
        or bars.empty
    ):

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

    # Compare with recent significant bars
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

    if (
        bars is None
        or bars.empty
    ):

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


def format_dollar_volume(value):

    value = safe_float(
        value
    )

    if value >= 1_000_000_000:

        return (
            f"${value / 1_000_000_000:.2f}B"
        )

    if value >= 1_000_000:

        return (
            f"${value / 1_000_000:.2f}M"
        )

    if value >= 1_000:

        return (
            f"${value / 1_000:.1f}K"
        )

    return f"${value:,.0f}"


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
        dict.fromkeys(symbols)
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

    scan_time = datetime.now(
        NY_TZ
    ).strftime("%H:%M:%S")

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

        # ====================================================
        # FILTERS
        # ====================================================

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
                "Time": scan_time,
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

    scan_time = datetime.now(
        NY_TZ
    ).strftime("%H:%M:%S")

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

        rows.append(
            {
                "Time": scan_time,
                "Symbol": symbol,
                "Price": price,
                "% Change": change,
                "RVOL": rvol,
                "Volume": volume,
                "$ Volume": dollar_volume,
                "Repeat": repeat
            }
        )

    if not rows:

        return pd.DataFrame()

    return pd.DataFrame(
        rows
    ).reset_index(
        drop=True
    )


# ============================================================
# SORTING
# ============================================================

def apply_sort(
    df,
    column,
    ascending
):

    if df is None or df.empty:

        return df

    if column not in df.columns:

        return df

    try:

        return (
            df
            .sort_values(
                by=column,
                ascending=ascending,
                kind="mergesort"
            )
            .reset_index(
                drop=True
            )
        )

    except Exception:

        return df


def toggle_regular_sort(column):

    current = (
        st.session_state.regular_sort_column
    )

    if current == column:

        st.session_state.regular_sort_ascending = (
            not st.session_state.regular_sort_ascending
        )

    else:

        st.session_state.regular_sort_column = (
            column
        )

        st.session_state.regular_sort_ascending = (
            False
        )


def toggle_watch_sort(column):

    current = (
        st.session_state.watch_sort_column
    )

    if current == column:

        st.session_state.watch_sort_ascending = (
            not st.session_state.watch_sort_ascending
        )

    else:

        st.session_state.watch_sort_column = (
            column
        )

        st.session_state.watch_sort_ascending = (
            False
        )


def sort_arrow(
    active,
    ascending
):

    if not active:

        return "↕"

    return "▲" if ascending else "▼"


# ============================================================
# REGULAR SORT HEADER
# ============================================================

def regular_sort_header():

    cols = st.columns(
        [
            1.00,  # Time
            1.15,  # Symbol
            1.00,  # Price
            1.15,  # %
            0.95,  # RVOL
            1.25,  # Volume
            1.35,  # $
            0.60   # Repeat
        ],
        gap="small"
    )

    columns = [
        ("Time", "TIME"),
        ("Symbol", "SYMBOL"),
        ("Price", "PRICE"),
        ("% Change", "%"),
        ("RVOL", "RVOL"),
        ("Volume", "VOLUME"),
        ("$ Volume", "$ VOL"),
        ("Repeat", "REP")
    ]

    for col, (
        column,
        label
    ) in zip(
        cols,
        columns
    ):

        active = (
            st.session_state.regular_sort_column
            == column
        )

        arrow = sort_arrow(
            active,
            st.session_state.regular_sort_ascending
        )

        with col:

            if st.button(
                f"{label} {arrow}",
                key=f"regular_sort_{column}",
                use_container_width=True
            ):

                toggle_regular_sort(
                    column
                )

                st.rerun()


# ============================================================
# WATCHLIST SORT HEADER
# ============================================================

def watch_sort_header():

    cols = st.columns(
        [
            1.00,
            1.15,
            1.00,
            1.15,
            0.95,
            1.25,
            1.35,
            0.60
        ],
        gap="small"
    )

    columns = [
        ("Time", "TIME"),
        ("Symbol", "SYMBOL"),
        ("Price", "PRICE"),
        ("% Change", "%"),
        ("RVOL", "RVOL"),
        ("Volume", "VOLUME"),
        ("$ Volume", "$ VOL"),
        ("Repeat", "REP")
    ]

    for col, (
        column,
        label
    ) in zip(
        cols,
        columns
    ):

        active = (
            st.session_state.watch_sort_column
            == column
        )

        arrow = sort_arrow(
            active,
            st.session_state.watch_sort_ascending
        )

        with col:

            if st.button(
                f"{label} {arrow}",
                key=f"watch_sort_{column}",
                use_container_width=True
            ):

                toggle_watch_sort(
                    column
                )

                st.rerun()


# ============================================================
# REGULAR RESULT ROW
# ============================================================

def render_regular_row(
    row,
    row_number
):

    symbol = str(
        row["Symbol"]
    )

    cols = st.columns(
        [
            1.00,
            1.15,
            1.00,
            1.15,
            0.95,
            1.25,
            1.35,
            0.60
        ],
        gap="small"
    )

    # TIME
    with cols[0]:

        st.markdown(
            f'<div class="row-text">'
            f'{row["Time"]}'
            f'</div>',
            unsafe_allow_html=True
        )

    # SYMBOL
    with cols[1]:

        if st.button(
            symbol,
            key=f"regular_symbol_{symbol}_{row_number}",
            use_container_width=True
        ):

            select_stock(
                symbol
            )

            st.rerun()

    # PRICE
    with cols[2]:

        price = safe_float(
            row["Price"]
        )

        st.markdown(
            f'<div class="row-text">'
            f'${price:.2f}'
            f'</div>',
            unsafe_allow_html=True
        )

    # CHANGE
    with cols[3]:

        change = safe_float(
            row["% Change"]
        )

        css_class = (
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
            f'<span class="{css_class}">'
            f'{prefix}{change:.2f}%'
            f'</span>',
            unsafe_allow_html=True
        )

    # RVOL
    with cols[4]:

        rvol = safe_float(
            row["RVOL"]
        )

        if rvol >= 3:

            st.markdown(
                f'<span class="green">'
                f'{rvol:.2f}x'
                f'</span>',
                unsafe_allow_html=True
            )

        elif rvol >= 2:

            st.markdown(
                f'<span class="yellow">'
                f'{rvol:.2f}x'
                f'</span>',
                unsafe_allow_html=True
            )

        else:

            st.write(
                f"{rvol:.2f}x"
            )

    # VOLUME
    with cols[5]:

        st.markdown(
            f'<div class="row-text">'
            f'{format_volume(row["Volume"])}'
            f'</div>',
            unsafe_allow_html=True
        )

    # DOLLAR VOLUME
    with cols[6]:

        st.markdown(
            f'<div class="row-text">'
            f'{format_dollar_volume(row["$ Volume"])}'
            f'</div>',
            unsafe_allow_html=True
        )

    # REPEAT
    with cols[7]:

        if bool(
            row["Repeat"]
        ):

            st.markdown(
                '<div class="repeat">■</div>',
                unsafe_allow_html=True
            )


# ============================================================
# WATCHLIST RESULT ROW
# ============================================================

def render_watch_row(
    row,
    row_number
):

    symbol = str(
        row["Symbol"]
    )

    cols = st.columns(
        [
            1.00,
            1.15,
            1.00,
            1.15,
            0.95,
            1.25,
            1.35,
            0.60
        ],
        gap="small"
    )

    with cols[0]:

        st.markdown(
            f'<div class="row-text">'
            f'{row["Time"]}'
            f'</div>',
            unsafe_allow_html=True
        )

    with cols[1]:

        if st.button(
            symbol,
            key=f"watch_symbol_{symbol}_{row_number}",
            use_container_width=True
        ):

            select_stock(
                symbol
            )

            st.rerun()

    with cols[2]:

        st.markdown(
            f'<div class="row-text">'
            f'${safe_float(row["Price"]):.2f}'
            f'</div>',
            unsafe_allow_html=True
        )

    with cols[3]:

        change = safe_float(
            row["% Change"]
        )

        css_class = (
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
            f'<span class="{css_class}">'
            f'{prefix}{change:.2f}%'
            f'</span>',
            unsafe_allow_html=True
        )

    with cols[4]:

        rvol = safe_float(
            row["RVOL"]
        )

        if rvol >= 3:

            st.markdown(
                f'<span class="green">'
                f'{rvol:.2f}x'
                f'</span>',
                unsafe_allow_html=True
            )

        elif rvol >= 2:

            st.markdown(
                f'<span class="yellow">'
                f'{rvol:.2f}x'
                f'</span>',
                unsafe_allow_html=True
            )

        else:

            st.write(
                f"{rvol:.2f}x"
            )

    with cols[5]:

        st.markdown(
            f'<div class="row-text">'
            f'{format_volume(row["Volume"])}'
            f'</div>',
            unsafe_allow_html=True
        )

    with cols[6]:

        st.markdown(
            f'<div class="row-text">'
            f'{format_dollar_volume(row["$ Volume"])}'
            f'</div>',
            unsafe_allow_html=True
        )

    with cols[7]:

        if bool(
            row["Repeat"]
        ):

            st.markdown(
                '<div class="repeat">■</div>',
                unsafe_allow_html=True
            )


# ============================================================
# MAIN 35 / 65 LAYOUT
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT SIDE
# ============================================================

with left:

    # Fixed 900px container.
    # This guarantees that the left panel and
    # TradingView chart are exactly the same height.

    with st.container(
        height=PANEL_HEIGHT,
        border=False
    ):

        st.markdown(
            '<div class="scanner-title">'
            'US STOCK SCANNER'
            '</div>',
            unsafe_allow_html=True
        )

        if WEBULL_CONNECTED:

            st.markdown(
                '<div class="connection">'
                '<span class="green">'
                '● Webull connected'
                '</span>'
                '</div>',
                unsafe_allow_html=True
            )

        else:

            st.error(
                "Webull connection failed."
            )

        # ====================================================
        # TABS
        # ====================================================

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

        # ====================================================
        # WATCHLIST
        # ====================================================

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
                    label_visibility="collapsed",
                    key="new_watch_symbol"
                )

            with col2:

                if st.button(
                    "ADD",
                    use_container_width=True,
                    key="add_watchlist"
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

                            st.rerun()

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

        # ====================================================
        # REGULAR SCAN
        # ====================================================

        with regular_tab:

            st.markdown(
                "### Regular Scan"
            )

            with st.expander(
                "Scanner Filters",
                expanded=False
            ):

                c1, c2 = st.columns(
                    2
                )

                with c1:

                    min_price = st.number_input(
                        "Minimum Price",
                        min_value=0.0,
                        value=1.0,
                        step=0.50,
                        key="min_price"
                    )

                    min_volume = st.number_input(
                        "Minimum Volume",
                        min_value=0,
                        value=100000,
                        step=10000,
                        key="min_volume"
                    )

                    min_rvol = st.number_input(
                        "Minimum RVOL",
                        min_value=0.0,
                        value=1.5,
                        step=0.1,
                        key="min_rvol"
                    )

                    min_change = st.number_input(
                        "Minimum % Change",
                        min_value=-100.0,
                        value=1.0,
                        step=0.5,
                        key="min_change"
                    )

                with c2:

                    max_price = st.number_input(
                        "Maximum Price",
                        min_value=0.0,
                        value=1000.0,
                        step=10.0,
                        key="max_price"
                    )

                    min_dollar_volume = st.number_input(
                        "Minimum $ Volume",
                        min_value=0,
                        value=1_000_000,
                        step=100000,
                        key="min_dollar_volume"
                    )

                    repeat_tolerance = st.number_input(
                        "Repeat Tolerance",
                        min_value=0.1,
                        max_value=2.0,
                        value=0.90,
                        step=0.05,
                        key="repeat_tolerance"
                    )

                    refresh_seconds = st.number_input(
                        "Refresh Seconds",
                        min_value=1,
                        value=60,
                        step=1,
                        key="refresh_seconds"
                    )

                max_symbols = st.number_input(
                    "Maximum Symbols",
                    min_value=1,
                    value=500,
                    step=50,
                    key="max_symbols"
                )

                auto_scan = st.checkbox(
                    "Auto Scan",
                    value=False,
                    key="auto_scan"
                )

                symbols_text = st.text_area(
                    "US Stock Symbols",
                    value=(
                        "AAPL,NVDA,AMD,PLTR,TSLA,"
                        "MSFT,AMZN,META,GOOGL,AVGO,"
                        "COIN,HOOD,SOFI"
                    ),
                    height=80,
                    key="symbols_text"
                )

            symbols = [
                x.strip().upper()
                for x in symbols_text.split(",")
                if x.strip()
            ]

            symbols = symbols[
                :int(max_symbols)
            ]

            # =================================================
            # SCAN BUTTONS
            # =================================================

            scan_col1, scan_col2 = st.columns(
                [3, 1]
            )

            with scan_col1:

                scan_clicked = st.button(
                    "SCAN NOW",
                    type="primary",
                    use_container_width=True,
                    key="regular_scan_button"
                )

            with scan_col2:

                clear_clicked = st.button(
                    "CLEAR",
                    use_container_width=True,
                    key="regular_clear_button"
                )

            if clear_clicked:

                st.session_state.regular_results = (
                    pd.DataFrame()
                )

                st.session_state.last_regular_scan = (
                    None
                )

                st.rerun()

            if scan_clicked:

                with st.spinner(
                    "Scanning..."
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
                        ).strftime(
                            "%H:%M:%S"
                        )
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

            # =================================================
            # SORT
            # =================================================

            results = apply_sort(
                results,
                st.session_state.regular_sort_column,
                st.session_state.regular_sort_ascending
            )

            # =================================================
            # SORTABLE HEADERS
            # =================================================

            regular_sort_header()

            st.markdown(
                "<hr style='margin:2px 0 3px 0;'>",
                unsafe_allow_html=True
            )

            # =================================================
            # RESULTS
            # =================================================

            if (
                results is not None
                and not results.empty
            ):

                for row_number, (_, row) in enumerate(
                    results.iterrows()
                ):

                    render_regular_row(
                        row,
                        row_number
                    )

            else:

                st.info(
                    "Run a scan to show stocks."
                )

        # ====================================================
        # WATCHLIST STOCK SCAN
        # ====================================================

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
                use_container_width=True,
                key="watchlist_scan_button"
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
                        ).strftime(
                            "%H:%M:%S"
                        )
                    )

            if st.session_state.last_watch_scan:

                st.caption(
                    "Last scan: "
                    + str(
                        st.session_state.last_watch_scan
                    )
                )

            watch_results = (
                st.session_state.watch_results
            )

            watch_results = apply_sort(
                watch_results,
                st.session_state.watch_sort_column,
                st.session_state.watch_sort_ascending
            )

            # =================================================
            # SORTABLE HEADERS
            # =================================================

            watch_sort_header()

            st.markdown(
                "<hr style='margin:2px 0 3px 0;'>",
                unsafe_allow_html=True
            )

            if (
                watch_results is not None
                and not watch_results.empty
            ):

                for row_number, (_, row) in enumerate(
                    watch_results.iterrows()
                ):

                    render_watch_row(
                        row,
                        row_number
                    )

            else:

                st.info(
                    "Run watchlist scan to show stocks."
                )


# ============================================================
# RIGHT SIDE
# TRADINGVIEW
# ============================================================

with right:

    selected = (
        st.session_state.selected_symbol
    )

    # IMPORTANT:
    # No heading, text or padding above this.
    # It begins at the same vertical level as
    # "US STOCK SCANNER" on the left.

    tradingview_chart(
        selected
    )
