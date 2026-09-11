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

button {
    font-size: 12px !important;
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

if "active_view" not in st.session_state:
    st.session_state.active_view = "Regular Scan"

if "scan_results" not in st.session_state:
    st.session_state.scan_results = pd.DataFrame()

if "watchlist" not in st.session_state:
    st.session_state.watchlist = []

if "watchlist_results" not in st.session_state:
    st.session_state.watchlist_results = pd.DataFrame()

if "repeat_results" not in st.session_state:
    st.session_state.repeat_results = pd.DataFrame()

if "volume_history" not in st.session_state:
    st.session_state.volume_history = {}


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
# INTRADAY DATA
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
# DAILY DATA
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
# DOLLAR VOLUME FORMAT
# =========================================================

def format_dollar_volume(value):

    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"

    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"

    return f"${value / 1_000:.0f}K"


# =========================================================
# RECORD VOLUME
# =========================================================

def record_volume(symbol, volume):

    if volume <= 0:
        return

    history = st.session_state.volume_history.get(
        symbol,
        []
    )

    history.append(float(volume))

    # Keep the last 20 observations
    if len(history) > 20:
        history = history[-20:]

    st.session_state.volume_history[symbol] = history


# =========================================================
# REPEAT CHECK
# =========================================================

def check_repeat(symbol, current_volume):

    history = st.session_state.volume_history.get(
        symbol,
        []
    )

    if not history:
        return False, None, 0

    tolerance = float(
        settings["repeat_tolerance"]
    )

    best_previous = None
    best_ratio = 0

    for previous_volume in history:

        if previous_volume <= 0:
            continue

        ratio = current_volume / previous_volume

        if ratio >= tolerance and ratio > best_ratio:

            best_ratio = ratio
            best_previous = previous_volume

    return (
        best_previous is not None,
        best_previous,
        best_ratio
    )


# =========================================================
# GET STOCK DATA
# =========================================================

def get_stock_data(symbol):

    try:

        intraday = get_intraday(symbol)

        if intraday is None or intraday.empty:
            return None

        daily = get_daily(symbol)

        if daily is None or daily.empty:
            return None

        # -------------------------------------------------
        # PRICE
        # -------------------------------------------------

        price = float(
            intraday["Close"].iloc[-1]
        )

        # -------------------------------------------------
        # VOLUME
        # -------------------------------------------------

        volume = float(
            intraday["Volume"]
            .fillna(0)
            .sum()
        )

        # -------------------------------------------------
        # PREVIOUS CLOSE
        # -------------------------------------------------

        if len(daily) >= 2:

            previous_close = float(
                daily["Close"].iloc[-2]
            )

        else:

            previous_close = price

        # -------------------------------------------------
        # CHANGE
        # -------------------------------------------------

        if previous_close > 0:

            change = (
                (price - previous_close)
                / previous_close
                * 100
            )

        else:

            change = 0

        # -------------------------------------------------
        # AVERAGE VOLUME
        # -------------------------------------------------

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

        # -------------------------------------------------
        # RVOL
        # -------------------------------------------------

        if avg_volume > 0:

            rvol = volume / avg_volume

        else:

            rvol = 0

        # -------------------------------------------------
        # DOLLAR VOLUME
        # -------------------------------------------------

        dollar_volume = price * volume

        return {
            "Symbol": symbol,
            "Price": price,
            "Change": change,
            "RVOL": rvol,
            "Volume": volume,
            "Dollar": dollar_volume
        }

    except Exception:

        return None


# =========================================================
# APPLY NORMAL FILTERS
# =========================================================

def passes_filters(data):

    if data is None:
        return False

    if data["Price"] < settings["min_price"]:
        return False

    if data["Price"] > settings["max_price"]:
        return False

    if data["Volume"] < settings["min_volume"]:
        return False

    if data["RVOL"] < settings["min_rvol"]:
        return False

    if data["Change"] < settings["min_change"]:
        return False

    if data["Dollar"] < settings["min_dollar_volume"]:
        return False

    return True


# =========================================================
# REGULAR MARKET SCAN
# =========================================================

def regular_scan():

    results = []

    for symbol in STOCKS:

        data = get_stock_data(symbol)

        if data is None:
            continue

        # Record volume for future repeat detection
        record_volume(
            symbol,
            data["Volume"]
        )

        if not passes_filters(data):
            continue

        repeat, previous_volume, ratio = check_repeat(
            symbol,
            data["Volume"]
        )

        data["Repeat"] = repeat

        results.append(data)

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    df = df.sort_values(
        ["Repeat", "RVOL", "Change"],
        ascending=[False, False, False]
    )

    return df


# =========================================================
# WATCHLIST DISPLAY SCAN
# =========================================================

def scan_watchlist_display():

    results = []

    for symbol in st.session_state.watchlist:

        data = get_stock_data(symbol)

        if data is None:
            continue

        repeat, previous_volume, ratio = check_repeat(
            symbol,
            data["Volume"]
        )

        data["Repeat"] = repeat

        results.append(data)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)


# =========================================================
# SCAN WATCHLIST FOR REPEAT VOLUME
# =========================================================

def scan_watchlist_repeat():

    results = []

    for symbol in st.session_state.watchlist:

        data = get_stock_data(symbol)

        if data is None:
            continue

        current_volume = data["Volume"]

        repeat, previous_volume, ratio = check_repeat(
            symbol,
            current_volume
        )

        data["Repeat"] = repeat

        data["PreviousVolume"] = (
            previous_volume
            if previous_volume is not None
            else 0
        )

        data["RepeatRatio"] = ratio

        results.append(data)

        # Record current observation AFTER comparison
        record_volume(
            symbol,
            current_volume
        )

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)

    df = df.sort_values(
        ["Repeat", "RepeatRatio", "RVOL", "Change"],
        ascending=[False, False, False, False]
    )

    return df


# =========================================================
# SIDEBAR
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

        st.success("🟢 Market Open")

    else:

        st.info("⚪ Market Closed")

with header3:

    if st.button(
        "🔄 Scan Now",
        use_container_width=True
    ):

        st.session_state.scan_results = regular_scan()

        if st.session_state.watchlist:

            st.session_state.watchlist_results = (
                scan_watchlist_display()
            )


# =========================================================
# INITIAL REGULAR SCAN
# =========================================================

if st.session_state.scan_results.empty:

    st.session_state.scan_results = regular_scan()


# =========================================================
# MAIN 35 / 65 LAYOUT
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
    # THREE COLUMN HEADINGS
    # =====================================================

    b1, b2, b3 = st.columns(
        [1, 1.2, 1.2]
    )


    # =====================================================
    # REGULAR SCAN BUTTON
    # =====================================================

    with b1:

        if st.button(
            "REGULAR SCAN",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.active_view == "Regular Scan"
                else "secondary"
            )
        ):

            st.session_state.active_view = "Regular Scan"

            st.rerun()


    # =====================================================
    # MY WATCHLIST BUTTON
    # =====================================================

    with b2:

        if st.button(
            "MY WATCHLIST",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.active_view == "My Watchlist"
                else "secondary"
            )
        ):

            st.session_state.active_view = "My Watchlist"

            st.rerun()


    # =====================================================
    # SCAN WATCHLIST BUTTON
    # =====================================================

    with b3:

        if st.button(
            "SCAN WATCHLIST",
            use_container_width=True,
            type=(
                "primary"
                if st.session_state.active_view == "Scan Watchlist"
                else "secondary"
            )
        ):

            st.session_state.active_view = "Scan Watchlist"

            # Immediately scan Watchlist
            if st.session_state.watchlist:

                st.session_state.repeat_results = (
                    scan_watchlist_repeat()
                )

            st.rerun()


    st.markdown("---")


    # =====================================================
    # REGULAR SCAN
    # =====================================================

    if st.session_state.active_view == "Regular Scan":

        st.markdown("#### 📋 Regular Market Scan")

        df = st.session_state.scan_results

        if df.empty:

            st.info(
                "No stocks match the filters."
            )

        else:

            # ---------------------------------------------
            # HEADER
            # ---------------------------------------------

            h0, h1, h2, h3, h4, h5 = st.columns(
                [0.45, 1.35, 1.0, 0.85, 0.9, 1.1]
            )

            h0.caption("WL")
            h1.caption("Symbol")
            h2.caption("LTP")
            h3.caption("%")
            h4.caption("RVOL")
            h5.caption("$Vol")


            # ---------------------------------------------
            # ROWS
            # ---------------------------------------------

            for _, row in df.iterrows():

                symbol = row["Symbol"]

                c0, c1, c2, c3, c4, c5 = st.columns(
                    [0.45, 1.35, 1.0, 0.85, 0.9, 1.1]
                )


                # -----------------------------------------
                # WATCHLIST
                # -----------------------------------------

                with c0:

                    if symbol in st.session_state.watchlist:

                        button_text = "★"

                    else:

                        button_text = "☆"

                    if st.button(
                        button_text,
                        key=f"wl_{symbol}",
                        help=(
                            "Remove from My Watchlist"
                            if symbol in st.session_state.watchlist
                            else "Add to My Watchlist"
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

                        symbol_label = (
                            f"■ {symbol}"
                        )

                    else:

                        symbol_label = symbol

                    if st.button(
                        symbol_label,
                        key=f"regular_symbol_{symbol}",
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
    # MY WATCHLIST
    # =====================================================

    elif st.session_state.active_view == "My Watchlist":

        st.markdown(
            f"#### ⭐ My Watchlist "
            f"({len(st.session_state.watchlist)})"
        )

        if not st.session_state.watchlist:

            st.info(
                "No stocks in My Watchlist."
            )

            st.caption(
                "Go to Regular Scan and click ☆ "
                "to add stocks."
            )

        else:

            # ---------------------------------------------
            # HEADER
            # ---------------------------------------------

            h0, h1, h2, h3, h4 = st.columns(
                [0.45, 1.45, 1.0, 0.9, 0.9]
            )

            h0.caption("")
            h1.caption("Symbol")
            h2.caption("LTP")
            h3.caption("%")
            h4.caption("RVOL")


            # ---------------------------------------------
            # WATCHLIST DATA
            # ---------------------------------------------

            watch_df = st.session_state.watchlist_results

            for symbol in st.session_state.watchlist:

                matching = pd.DataFrame()

                if (
                    watch_df is not None
                    and not watch_df.empty
                    and "Symbol" in watch_df.columns
                ):

                    matching = watch_df[
                        watch_df["Symbol"] == symbol
                    ]


                c0, c1, c2, c3, c4 = st.columns(
                    [0.45, 1.45, 1.0, 0.9, 0.9]
                )


                # -----------------------------------------
                # REMOVE
                # -----------------------------------------

                with c0:

                    if st.button(
                        "×",
                        key=f"remove_wl_{symbol}",
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
                        key=f"watch_symbol_{symbol}",
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


            st.markdown("")


            # ---------------------------------------------
            # REMOVE ALL
            # ---------------------------------------------

            if st.button(
                "🗑 Clear Watchlist",
                use_container_width=True
            ):

                st.session_state.watchlist = []

                st.session_state.watchlist_results = (
                    pd.DataFrame()
                )

                st.session_state.repeat_results = (
                    pd.DataFrame()
                )

                st.rerun()


    # =====================================================
    # SCAN WATCHLIST
    # =====================================================

    elif st.session_state.active_view == "Scan Watchlist":

        st.markdown(
            "#### 🔁 Scan Watchlist"
        )

        st.caption(
            "Repeat-volume scanner — Watchlist stocks only"
        )


        # ---------------------------------------------
        # MANUAL SCAN BUTTON
        # ---------------------------------------------

        if st.button(
            "🔄 Scan Watchlist Now",
            use_container_width=True
        ):

            if st.session_state.watchlist:

                st.session_state.repeat_results = (
                    scan_watchlist_repeat()
                )

                st.rerun()

            else:

                st.warning(
                    "Your Watchlist is empty."
                )


        repeat_df = st.session_state.repeat_results


        # ---------------------------------------------
        # EMPTY WATCHLIST
        # ---------------------------------------------

        if not st.session_state.watchlist:

            st.info(
                "Add stocks to My Watchlist first."
            )


        # ---------------------------------------------
        # RESULTS
        # ---------------------------------------------

        elif repeat_df.empty:

            st.info(
                "Press 'Scan Watchlist Now' "
                "to scan your Watchlist."
            )

        else:

            # ---------------------------------------------
            # HEADER
            # ---------------------------------------------

            h1, h2, h3, h4, h5, h6 = st.columns(
                [1.35, 0.9, 0.85, 0.85, 1.0, 0.9]
            )

            h1.caption("Symbol")
            h2.caption("LTP")
            h3.caption("%")
            h4.caption("RVOL")
            h5.caption("Volume")
            h6.caption("Repeat")


            # ---------------------------------------------
            # RESULTS
            # ---------------------------------------------

            for _, row in repeat_df.iterrows():

                symbol = row["Symbol"]

                c1, c2, c3, c4, c5, c6 = st.columns(
                    [1.35, 0.9, 0.85, 0.85, 1.0, 0.9]
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
                        key=f"repeat_symbol_{symbol}",
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

                    elif volume >= 1_000:

                        text = (
                            f"{volume / 1_000:.0f}K"
                        )

                    else:

                        text = str(
                            int(volume)
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
