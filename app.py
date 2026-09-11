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

button {
    font-size: 12px !important;
}

.watchlist-count {
    font-size: 11px;
    opacity: 0.7;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# STOCK UNIVERSE
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

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "AAPL"

if "previous_volumes" not in st.session_state:
    st.session_state.previous_volumes = {}

if "volume_history" not in st.session_state:
    st.session_state.volume_history = {}

if "scan_results" not in st.session_state:
    st.session_state.scan_results = pd.DataFrame()

if "repeat_results" not in st.session_state:
    st.session_state.repeat_results = pd.DataFrame()

if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

if "active_view" not in st.session_state:
    st.session_state.active_view = "Scanner"


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

    except Exception:
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

    except Exception:
        return None


# =========================================================
# FORMAT DOLLAR VOLUME
# =========================================================

def format_dollar_volume(dollar):

    if dollar >= 1_000_000_000:
        return f"${dollar / 1_000_000_000:.1f}B"

    elif dollar >= 1_000_000:
        return f"${dollar / 1_000_000:.1f}M"

    else:
        return f"${dollar / 1_000:.0f}K"


# =========================================================
# REPEAT VOLUME
# =========================================================
#
# This keeps a history of scan volumes for every symbol.
#
# A repeat signal is generated when the current volume
# reaches at least the selected percentage of a previous
# recorded volume.
#
# Example:
#
# previous volume = 2,000,000
# tolerance       = 0.90
# current volume  = 1,900,000
#
# 1,900,000 / 2,000,000 = 0.95
#
# Therefore repeat = True
# =========================================================

def update_volume_history(symbol, current_volume):

    if current_volume <= 0:
        return False

    history = st.session_state.volume_history.get(symbol, [])

    repeat = False

    tolerance = float(settings["repeat_tolerance"])

    # Compare current volume with previous meaningful
    # volume observations.
    if history:

        for previous_volume in history:

            if previous_volume <= 0:
                continue

            ratio = current_volume / previous_volume

            if ratio >= tolerance:
                repeat = True
                break

    # Keep only recent history.
    history.append(float(current_volume))

    if len(history) > 20:
        history = history[-20:]

    st.session_state.volume_history[symbol] = history

    st.session_state.previous_volumes[symbol] = current_volume

    return repeat


# =========================================================
# NORMAL SCANNER
# =========================================================

def scan_symbols(symbols):

    results = []

    for symbol in symbols:

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

            price = float(
                intraday["Close"].iloc[-1]
            )

            # ---------------------------------------------
            # VOLUME
            # ---------------------------------------------

            volume = float(
                intraday["Volume"]
                .fillna(0)
                .sum()
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
                    daily["Volume"]
                    .iloc[-6:-1]
                    .mean()
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

            repeat = update_volume_history(
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

        except Exception:
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
# NORMAL SCAN
# =========================================================

def scan_stocks():

    return scan_symbols(STOCKS)


# =========================================================
# WATCHLIST REPEAT SCAN
# =========================================================

def scan_watchlist_repeat():

    if not st.session_state.watchlist:

        return pd.DataFrame()

    results = []

    for symbol in st.session_state.watchlist:

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

            price = float(
                intraday["Close"].iloc[-1]
            )

            # ---------------------------------------------
            # CURRENT TOTAL VOLUME
            # ---------------------------------------------

            volume = float(
                intraday["Volume"]
                .fillna(0)
                .sum()
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
            # DAILY AVERAGE VOLUME
            # ---------------------------------------------

            if len(daily) >= 6:

                avg_volume = float(
                    daily["Volume"]
                    .iloc[-6:-1]
                    .mean()
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
            # HISTORY
            # ---------------------------------------------

            history = st.session_state.volume_history.get(
                symbol,
                []
            )

            repeat = False
            previous_volume = None
            repeat_ratio = 0

            if history:

                tolerance = float(
                    settings["repeat_tolerance"]
                )

                for old_volume in reversed(history):

                    if old_volume <= 0:
                        continue

                    ratio = volume / old_volume

                    if ratio >= tolerance:

                        repeat = True
                        previous_volume = old_volume
                        repeat_ratio = ratio
                        break

            results.append({
                "Symbol": symbol,
                "Price": price,
                "Change": change,
                "RVOL": rvol,
                "Volume": volume,
                "Dollar": dollar_volume,
                "Repeat": repeat,
                "PreviousVolume": previous_volume,
                "RepeatRatio": repeat_ratio
            })

            # Update history after comparison.
            history.append(float(volume))

            if len(history) > 20:
                history = history[-20:]

            st.session_state.volume_history[symbol] = history

        except Exception:
            continue

    if not results:

        return pd.DataFrame()

    df = pd.DataFrame(results)

    df = df.sort_values(
        ["Repeat", "RepeatRatio", "RVOL"],
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

    if st.button(
        "💾 Save Filters",
        use_container_width=True
    ):

        save_settings()

        st.success("Saved")


# =========================================================
# HEADER
# =========================================================

header1, header2, header3 = st.columns(
    [5, 2, 2]
)

with header1:

    st.markdown(
        "## 📈 US Momentum Stock Scanner"
    )

with header2:

    if market_open():

        st.success(
            "🟢 Market Open"
        )

    else:

        st.info(
            "⚪ Market Closed"
        )

with header3:

    if st.button(
        "🔄 Scan Now",
        use_container_width=True
    ):

        # Always perform normal market scan
        st.session_state.scan_results = scan_stocks()

        # Also refresh repeat scanner
        if st.session_state.watchlist:

            st.session_state.repeat_results = (
                scan_watchlist_repeat()
            )


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
# LEFT 35%
# =========================================================

with left:

    # =====================================================
    # THREE COLUMN HEADINGS / TABS
    # =====================================================

    tab1, tab2, tab3 = st.columns(
        [1, 1.2, 1]
    )

    with tab1:

        if st.button(
            "SCANNER",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.active_view == "Scanner"
                else "secondary"
            )
        ):

            st.session_state.active_view = "Scanner"
            st.rerun()

    with tab2:

        if st.button(
            "MY WATCHLIST",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.active_view == "Watchlist"
                else "secondary"
            )
        ):

            st.session_state.active_view = "Watchlist"
            st.rerun()

    with tab3:

        if st.button(
            "REPEAT SCAN",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.active_view == "Repeat"
                else "secondary"
            )
        ):

            st.session_state.active_view = "Repeat"
            st.rerun()


    st.markdown("---")


    # =====================================================
    # SCANNER VIEW
    # =====================================================

    if st.session_state.active_view == "Scanner":

        st.markdown(
            "#### 📋 Market Scanner"
        )

        if df.empty:

            st.info(
                "No stocks match the filters."
            )

        else:

            # ---------------------------------------------
            # TABLE HEADER
            # ---------------------------------------------

            h0, h1, h2, h3, h4, h5 = st.columns(
                [0.45, 1.35, 1.1, 0.9, 0.9, 1.15]
            )

            h0.caption("")

            h1.caption("Symbol")
            h2.caption("LTP")
            h3.caption("%")
            h4.caption("RVOL")
            h5.caption("$Vol")


            # ---------------------------------------------
            # STOCK ROWS
            # ---------------------------------------------

            for _, row in df.iterrows():

                symbol = row["Symbol"]

                c0, c1, c2, c3, c4, c5 = st.columns(
                    [0.45, 1.35, 1.1, 0.9, 0.9, 1.15]
                )

                # -----------------------------------------
                # WATCHLIST BUTTON
                # -----------------------------------------

                with c0:

                    if symbol in st.session_state.watchlist:

                        remove_label = "★"

                    else:

                        remove_label = "☆"

                    if st.button(
                        remove_label,
                        key=f"watch_{symbol}",
                        help=(
                            "Remove from Watchlist"
                            if symbol in st.session_state.watchlist
                            else "Add to Watchlist"
                        )
                    ):

                        if symbol in st.session_state.watchlist:

                            st.session_state.watchlist.remove(
                                symbol
                            )

                        else:

                            st.session_state.watchlist.append(
                                symbol
                            )

                        st.rerun()


                # -----------------------------------------
                # SYMBOL
                # -----------------------------------------

                with c1:

                    if row["Repeat"]:

                        label = f"■ {symbol}"

                    else:

                        label = symbol

                    if st.button(
                        label,
                        key=f"select_scanner_{symbol}",
                        use_container_width=True
                    ):

                        st.session_state.selected_symbol = symbol

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
                        format_dollar_volume(
                            row["Dollar"]
                        )
                    )


    # =====================================================
    # MY WATCHLIST VIEW
    # =====================================================

    elif st.session_state.active_view == "Watchlist":

        st.markdown(
            f"#### ⭐ My Watchlist "
            f"({len(st.session_state.watchlist)})"
        )

        if not st.session_state.watchlist:

            st.info(
                "Your Watchlist is empty. "
                "Use ☆ beside a stock in Scanner to add it."
            )

        else:

            # ---------------------------------------------
            # HEADER
            # ---------------------------------------------

            h0, h1, h2, h3, h4 = st.columns(
                [0.45, 1.45, 1.1, 1, 1]
            )

            h0.caption("")
            h1.caption("Symbol")
            h2.caption("LTP")
            h3.caption("%")
            h4.caption("RVOL")


            # ---------------------------------------------
            # GET DATA FROM NORMAL SCAN FIRST
            # ---------------------------------------------

            watch_df = df[
                df["Symbol"].isin(
                    st.session_state.watchlist
                )
            ].copy()


            # ---------------------------------------------
            # WATCHLIST ROWS
            # ---------------------------------------------

            for symbol in st.session_state.watchlist:

                matching = watch_df[
                    watch_df["Symbol"] == symbol
                ]

                c0, c1, c2, c3, c4 = st.columns(
                    [0.45, 1.45, 1.1, 1, 1]
                )

                # -----------------------------------------
                # REMOVE
                # -----------------------------------------

                with c0:

                    if st.button(
                        "×",
                        key=f"remove_{symbol}",
                        help="Remove from Watchlist"
                    ):

                        st.session_state.watchlist.remove(
                            symbol
                        )

                        st.rerun()


                # -----------------------------------------
                # SYMBOL
                # -----------------------------------------

                with c1:

                    if st.button(
                        symbol,
                        key=f"select_watch_{symbol}",
                        use_container_width=True
                    ):

                        st.session_state.selected_symbol = symbol

                        st.rerun()


                # -----------------------------------------
                # DATA
                # -----------------------------------------

                if not matching.empty:

                    row = matching.iloc[0]

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


            # ---------------------------------------------
            # CLEAR WATCHLIST
            # ---------------------------------------------

            st.markdown("")

            if st.button(
                "🗑 Clear Watchlist",
                use_container_width=True
            ):

                st.session_state.watchlist = []

                st.rerun()


    # =====================================================
    # REPEAT SCAN VIEW
    # =====================================================

    elif st.session_state.active_view == "Repeat":

        st.markdown(
            "#### 🔁 Repeat Volume Scan"
        )

        st.caption(
            "Only stocks in My Watchlist are monitored here."
        )


        # ---------------------------------------------
        # RUN REPEAT SCAN
        # ---------------------------------------------

        if st.button(
            "🔁 Scan Watchlist",
            use_container_width=True
        ):

            st.session_state.repeat_results = (
                scan_watchlist_repeat()
            )

            st.rerun()


        repeat_df = st.session_state.repeat_results


        # ---------------------------------------------
        # NO WATCHLIST
        # ---------------------------------------------

        if not st.session_state.watchlist:

            st.info(
                "Add stocks to My Watchlist first."
            )


        # ---------------------------------------------
        # NO RESULTS
        # ---------------------------------------------

        elif repeat_df.empty:

            st.info(
                "No repeat-volume data yet. "
                "Run Scan Watchlist."
            )


        # ---------------------------------------------
        # RESULTS
        # ---------------------------------------------

        else:

            h1, h2, h3, h4, h5, h6 = st.columns(
                [1.25, 0.95, 0.8, 0.9, 1.0, 0.8]
            )

            h1.caption("Symbol")
            h2.caption("LTP")
            h3.caption("%")
            h4.caption("RVOL")
            h5.caption("Volume")
            h6.caption("Repeat")


            for _, row in repeat_df.iterrows():

                symbol = row["Symbol"]

                c1, c2, c3, c4, c5, c6 = st.columns(
                    [1.25, 0.95, 0.8, 0.9, 1.0, 0.8]
                )


                # -----------------------------------------
                # SYMBOL
                # -----------------------------------------

                with c1:

                    if row["Repeat"]:

                        label = f"■ {symbol}"

                    else:

                        label = symbol

                    if st.button(
                        label,
                        key=f"select_repeat_{symbol}",
                        use_container_width=True
                    ):

                        st.session_state.selected_symbol = symbol

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
                # VOLUME
                # -----------------------------------------

                with c5:

                    volume = row["Volume"]

                    if volume >= 1_000_000:

                        text = (
                            f"{volume / 1_000_000:.1f}M"
                        )

                    else:

                        text = (
                            f"{volume / 1_000:.0f}K"
                        )

                    st.caption(text)


                # -----------------------------------------
                # REPEAT
                # -----------------------------------------

                with c6:

                    if row["Repeat"]:

                        st.markdown(
                            "■ **YES**"
                        )

                    else:

                        st.caption("—")


# =========================================================
# RIGHT 65% - TRADINGVIEW
# =========================================================

with right:

    symbol = st.session_state.selected_symbol

    interval = settings["chart_interval"]

    st.markdown(
        f"### 📊 {symbol}"
    )


    # =====================================================
    # TRADINGVIEW
    # =====================================================

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
