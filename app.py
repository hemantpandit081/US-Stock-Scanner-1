import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import os
import json
from datetime import datetime, time
from zoneinfo import ZoneInfo
import streamlit.components.v1 as components


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="US Momentum Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# 30 STOCKS
# ============================================================

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


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 100% !important;
        width: 100% !important;
        padding-top: 0.35rem !important;
        padding-bottom: 0.2rem !important;
        padding-left: 0.35rem !important;
        padding-right: 0.35rem !important;
    }

    .main-title {
        font-size: 22px;
        font-weight: 800;
        margin-bottom: 0px;
        line-height: 1.1;
    }

    .sub-title {
        font-size: 11px;
        opacity: 0.65;
        margin-bottom: 5px;
    }

    .scanner-header {
        font-size: 9px;
        font-weight: 800;
        padding-top: 3px;
        padding-bottom: 3px;
        white-space: nowrap;
        overflow: hidden;
    }

    .scanner-row {
        font-size: 9px;
        padding-top: 2px;
        padding-bottom: 2px;
        white-space: nowrap;
        overflow: hidden;
    }

    .repeat-square {
        font-size: 15px;
        font-weight: 900;
        line-height: 1;
        color: white;
        margin-top: 3px;
        text-align: center;
    }

    div.stButton > button {
        min-height: 23px !important;
        height: 23px !important;
        padding: 0px 2px !important;
        font-size: 9px !important;
        font-weight: 700 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: clip !important;
    }

    section[data-testid="stSidebar"] {
        min-width: 260px !important;
        max-width: 280px !important;
    }

    div[data-testid="stVerticalBlock"] {
        gap: 0.12rem;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SETTINGS
# ============================================================

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

NY_TZ = ZoneInfo("America/New_York")


# ============================================================
# LOAD SETTINGS
# ============================================================

def load_settings():

    if os.path.exists(SETTINGS_FILE):

        try:

            with open(
                SETTINGS_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                saved = json.load(f)

            settings = DEFAULT_SETTINGS.copy()
            settings.update(saved)

            return settings

        except Exception:

            pass

    return DEFAULT_SETTINGS.copy()


# ============================================================
# SAVE SETTINGS
# ============================================================

def save_settings(settings):

    try:

        with open(
            SETTINGS_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                settings,
                f,
                indent=4
            )

        return True

    except Exception:

        return False


# ============================================================
# SESSION STATE
# ============================================================

if "settings" not in st.session_state:

    st.session_state.settings = load_settings()


if "selected_ticker" not in st.session_state:

    st.session_state.selected_ticker = "NVDA"


if "scanner_data" not in st.session_state:

    st.session_state.scanner_data = pd.DataFrame()


if "last_scan" not in st.session_state:

    st.session_state.last_scan = None


if "previous_volumes" not in st.session_state:

    st.session_state.previous_volumes = {}


# ============================================================
# MARKET HOURS
# ============================================================

def market_is_open():

    now = datetime.now(NY_TZ)

    if now.weekday() >= 5:
        return False

    market_open = time(9, 30)
    market_close = time(16, 0)

    return (
        market_open
        <= now.time()
        <= market_close
    )


# ============================================================
# GET SYMBOL DATA
# ============================================================

def get_symbol_data(data, symbol):

    if data is None or data.empty:
        return None

    try:

        if isinstance(
            data.columns,
            pd.MultiIndex
        ):

            if symbol in data.columns.get_level_values(0):

                result = data[symbol].copy()

            elif symbol in data.columns.get_level_values(1):

                result = data.xs(
                    symbol,
                    axis=1,
                    level=1
                ).copy()

            else:

                return None

        else:

            result = data.copy()

        return result.dropna(
            how="all"
        )

    except Exception:

        return None


# ============================================================
# REPEAT VOLUME
# ============================================================

def detect_repeat_volume(
    symbol,
    current_volume,
    tolerance
):

    previous = (
        st.session_state.previous_volumes
        .get(symbol)
    )

    if previous is None:
        return False

    if previous <= 0:
        return False

    current_volume = float(
        current_volume
    )

    previous = float(
        previous
    )

    ratio = (
        current_volume
        / previous
    )

    near_same = (
        ratio >= tolerance
        and
        ratio <= (2.0 - tolerance)
    )

    higher = (
        current_volume > previous
    )

    return (
        near_same
        or higher
    )


# ============================================================
# SCAN ALL 30 STOCKS
# ============================================================

def run_scanner():

    settings = (
        st.session_state.settings
    )

    symbols = STOCKS


    # ========================================================
    # DOWNLOAD 1 MINUTE DATA
    # ========================================================

    try:

        intraday = yf.download(
            tickers=symbols,
            period="1d",
            interval="1m",
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            threads=True,
            progress=False
        )

    except Exception:

        intraday = pd.DataFrame()


    # ========================================================
    # DOWNLOAD DAILY DATA
    # ========================================================

    try:

        daily = yf.download(
            tickers=symbols,
            period="20d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            prepost=False,
            threads=True,
            progress=False
        )

    except Exception:

        daily = pd.DataFrame()


    results = []


    # ========================================================
    # PROCESS EACH STOCK
    # ========================================================

    for symbol in symbols:

        try:

            minute_data = get_symbol_data(
                intraday,
                symbol
            )

            daily_data = get_symbol_data(
                daily,
                symbol
            )


            if (
                minute_data is None
                or minute_data.empty
            ):

                continue


            if not all(
                col in minute_data.columns
                for col in [
                    "Close",
                    "Volume"
                ]
            ):

                continue


            minute_data = (
                minute_data
                .dropna(
                    subset=["Close"]
                )
            )


            if minute_data.empty:
                continue


            # =================================================
            # LTP
            # =================================================

            ltp = float(
                minute_data["Close"].iloc[-1]
            )


            if ltp <= 0:
                continue


            # =================================================
            # CURRENT SESSION
            # =================================================

            latest_date = (
                minute_data
                .index[-1]
                .date()
            )


            session_data = (
                minute_data[
                    minute_data.index.date
                    == latest_date
                ]
                .copy()
            )


            if session_data.empty:
                continue


            # =================================================
            # SESSION VOLUME
            # =================================================

            session_volume = float(
                pd.to_numeric(
                    session_data["Volume"],
                    errors="coerce"
                )
                .fillna(0)
                .sum()
            )


            if session_volume <= 0:
                continue


            # =================================================
            # PREVIOUS CLOSE
            # =================================================

            previous_close = np.nan


            if (
                daily_data is not None
                and not daily_data.empty
                and "Close" in daily_data.columns
            ):

                closes = (
                    pd.to_numeric(
                        daily_data["Close"],
                        errors="coerce"
                    )
                    .dropna()
                )

                if len(closes) >= 2:

                    previous_close = float(
                        closes.iloc[-2]
                    )


            if (
                pd.isna(previous_close)
                or previous_close <= 0
            ):

                continue


            # =================================================
            # % CHANGE
            # =================================================

            percent_change = (
                (
                    ltp
                    - previous_close
                )
                / previous_close
                * 100
            )


            # =================================================
            # AVERAGE DAILY VOLUME
            # =================================================

            avg_volume = np.nan


            if (
                daily_data is not None
                and not daily_data.empty
                and "Volume" in daily_data.columns
            ):

                daily_volumes = (
                    pd.to_numeric(
                        daily_data["Volume"],
                        errors="coerce"
                    )
                    .dropna()
                )

                if len(daily_volumes) >= 2:

                    avg_volume = float(
                        daily_volumes
                        .iloc[:-1]
                        .tail(5)
                        .mean()
                    )


            # =================================================
            # RVOL
            # =================================================

            if (
                pd.isna(avg_volume)
                or avg_volume <= 0
            ):

                rel_volume = 0.0

            else:

                rel_volume = (
                    session_volume
                    / avg_volume
                )


            # =================================================
            # PRICE × VOLUME
            # =================================================

            dollar_volume = (
                ltp
                * session_volume
            )


            # =================================================
            # REPEAT SIGNAL
            # =================================================

            repeat = detect_repeat_volume(
                symbol,
                session_volume,
                settings[
                    "repeat_tolerance"
                ]
            )


            # =================================================
            # FILTER
            # =================================================

            if ltp < settings["min_price"]:
                continue

            if ltp > settings["max_price"]:
                continue

            if session_volume < settings["min_volume"]:
                continue

            if rel_volume < settings["min_rvol"]:
                continue

            if percent_change < settings["min_change"]:
                continue

            if dollar_volume < settings["min_dollar_volume"]:
                continue


            # =================================================
            # ADD RESULT
            # =================================================

            results.append(
                {
                    "Time":
                        session_data.index[-1],

                    "Symbol":
                        symbol,

                    "LTP":
                        ltp,

                    "% Change":
                        percent_change,

                    "Rel Vol":
                        rel_volume,

                    "Volume":
                        session_volume,

                    "Dollar Volume":
                        dollar_volume,

                    "Repeat":
                        bool(repeat)
                }
            )


        except Exception:

            continue


    # ========================================================
    # NO RESULTS
    # ========================================================

    if not results:

        return pd.DataFrame()


    result = pd.DataFrame(
        results
    )


    # ========================================================
    # SAVE CURRENT VOLUMES
    # ========================================================

    for _, row in result.iterrows():

        st.session_state.previous_volumes[
            row["Symbol"]
        ] = float(
            row["Volume"]
        )


    # ========================================================
    # SORT
    # ========================================================

    result = result.sort_values(
        by=[
            "Repeat",
            "Rel Vol",
            "% Change"
        ],
        ascending=[
            False,
            False,
            False
        ]
    )


    return result.reset_index(
        drop=True
    )


# ============================================================
# TRADINGVIEW CHART
# ============================================================

def tradingview_chart(
    symbol,
    interval,
    height=700
):

    html = f"""
    <div
        style="
            width:100%;
            height:{height}px;
        "
    >

        <div
            class="tradingview-widget-container"
            style="
                width:100%;
                height:100%;
            "
        >

            <div
                class="tradingview-widget-container__widget"
                style="
                    width:100%;
                    height:100%;
                "
            >
            </div>

            <script
                type="text/javascript"
                src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
                async
            >
            {{
                "autosize": true,
                "symbol": "{symbol}",
                "interval": "{interval}",
                "timezone": "America/New_York",
                "theme": "dark",
                "style": "1",
                "withdateranges": true,
                "hide_side_toolbar": false,
                "allow_symbol_change": true,
                "save_image": true,
                "hide_volume": false,
                "hide_legend": false,
                "calendar": false,
                "studies": [],
                "locale": "en",
                "support_host": "https://www.tradingview.com"
            }}
            </script>

        </div>

    </div>
    """


    components.html(
        html,
        height=height,
        scrolling=False
    )


# ============================================================
# TITLE
# ============================================================

st.markdown(
    """
    <div class="main-title">
        📈 US Momentum Stock Scanner
    </div>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
    <div class="sub-title">
        1-minute momentum scanner • 30 US Stocks • TradingView
    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header(
        "Scanner Settings"
    )


    # ========================================================
    # AUTO SCAN
    # ========================================================

    auto_scan = st.checkbox(
        "Automatic Scanner",
        value=st.session_state.settings[
            "auto_scan"
        ]
    )


    # ========================================================
    # REFRESH
    # ========================================================

    refresh_options = [
        30,
        60,
        90,
        120,
        180,
        300
    ]


    current_refresh = int(
        st.session_state.settings[
            "refresh_seconds"
        ]
    )


    if current_refresh not in refresh_options:

        current_refresh = 60


    refresh_seconds = st.selectbox(
        "Refresh interval",
        refresh_options,
        index=refresh_options.index(
            current_refresh
        )
    )


    st.divider()


    # ========================================================
    # PRICE
    # ========================================================

    min_price = st.number_input(
        "Minimum price",
        min_value=0.01,
        value=float(
            st.session_state.settings[
                "min_price"
            ]
        ),
        step=0.50
    )


    max_price = st.number_input(
        "Maximum price",
        min_value=0.01,
        value=float(
            st.session_state.settings[
                "max_price"
            ]
        ),
        step=1.00
    )


    # ========================================================
    # VOLUME
    # ========================================================

    min_volume = st.number_input(
        "Minimum volume",
        min_value=0,
        value=int(
            st.session_state.settings[
                "min_volume"
            ]
        ),
        step=100000
    )


    # ========================================================
    # RVOL
    # ========================================================

    min_rvol = st.number_input(
        "Minimum Relative Volume",
        min_value=0.0,
        value=float(
            st.session_state.settings[
                "min_rvol"
            ]
        ),
        step=0.5
    )


    # ========================================================
    # CHANGE
    # ========================================================

    min_change = st.number_input(
        "Minimum % Change",
        value=float(
            st.session_state.settings[
                "min_change"
            ]
        ),
        step=0.5
    )


    # ========================================================
    # DOLLAR VOLUME
    # ========================================================

    min_dollar_volume = st.number_input(
        "Minimum Price × Volume",
        min_value=0,
        value=int(
            st.session_state.settings[
                "min_dollar_volume"
            ]
        ),
        step=1000000
    )


    # ========================================================
    # REPEAT
    # ========================================================

    repeat_percent = st.slider(
        "Repeat volume threshold",
        min_value=50,
        max_value=100,
        value=int(
            st.session_state.settings[
                "repeat_tolerance"
            ] * 100
        ),
        step=5
    )


    st.divider()


    # ========================================================
    # CHART INTERVAL
    # ========================================================

    chart_options = {
        "1": "1 Minute",
        "5": "5 Minutes",
        "15": "15 Minutes",
        "30": "30 Minutes",
        "60": "1 Hour",
        "240": "4 Hours",
        "D": "1 Day"
    }


    current_interval = (
        st.session_state.settings[
            "chart_interval"
        ]
    )


    if current_interval not in chart_options:

        current_interval = "1"


    chart_interval = st.selectbox(
        "Chart interval",
        options=list(
            chart_options.keys()
        ),
        index=list(
            chart_options.keys()
        ).index(
            current_interval
        ),
        format_func=lambda x:
            chart_options[x]
    )


    st.divider()


    # ========================================================
    # SAVE SETTINGS
    # ========================================================

    if st.button(
        "💾 Save Settings",
        use_container_width=True
    ):

        st.session_state.settings = {

            "min_price":
                float(min_price),

            "max_price":
                float(max_price),

            "min_volume":
                int(min_volume),

            "min_rvol":
                float(min_rvol),

            "min_change":
                float(min_change),

            "min_dollar_volume":
                int(min_dollar_volume),

            "repeat_tolerance":
                float(
                    repeat_percent / 100
                ),

            "refresh_seconds":
                int(refresh_seconds),

            "auto_scan":
                bool(auto_scan),

            "chart_interval":
                chart_interval
        }


        save_settings(
            st.session_state.settings
        )


        st.success(
            "Settings saved"
        )


    # ========================================================
    # SCAN NOW
    # ========================================================

    if st.button(
        "🔎 Scan Now",
        use_container_width=True
    ):

        st.session_state.settings = {

            "min_price":
                float(min_price),

            "max_price":
                float(max_price),

            "min_volume":
                int(min_volume),

            "min_rvol":
                float(min_rvol),

            "min_change":
                float(min_change),

            "min_dollar_volume":
                int(min_dollar_volume),

            "repeat_tolerance":
                float(
                    repeat_percent / 100
                ),

            "refresh_seconds":
                int(refresh_seconds),

            "auto_scan":
                bool(auto_scan),

            "chart_interval":
                chart_interval
        }


        with st.spinner(
            "Scanning 30 stocks..."
        ):

            st.session_state.scanner_data = (
                run_scanner()
            )


        st.session_state.last_scan = (
            datetime.now()
        )


        st.rerun()


# ============================================================
# AUTO REFRESH
# ============================================================

run_every = None


if (
    st.session_state.settings[
        "auto_scan"
    ]
    and market_is_open()
):

    run_every = (
        f'{st.session_state.settings["refresh_seconds"]}s'
    )


# ============================================================
# MAIN APPLICATION
# ============================================================

@st.fragment(
    run_every=run_every
)
def automatic_scanner():

    # ========================================================
    # AUTOMATIC SCAN
    # ========================================================

    if (
        st.session_state.settings[
            "auto_scan"
        ]
        and market_is_open()
    ):

        with st.spinner(
            "Updating scanner..."
        ):

            st.session_state.scanner_data = (
                run_scanner()
            )


        st.session_state.last_scan = (
            datetime.now()
        )


    data = (
        st.session_state.scanner_data
    )


    # ========================================================
    # 35% LEFT / 65% RIGHT
    # ========================================================

    left_col, right_col = st.columns(
        [3.5, 6.5],
        gap="small"
    )


    # ========================================================
    # LEFT — 35% SCANNER
    # ========================================================

    with left_col:

        st.markdown(
            "### Scanner"
        )


        if (
            st.session_state.last_scan
            is not None
        ):

            st.caption(
                "Updated "
                +
                st.session_state.last_scan.strftime(
                    "%H:%M:%S"
                )
            )


        if (
            data is None
            or data.empty
        ):

            st.info(
                "No stocks match your filters."
            )

        else:

            # =================================================
            # HEADER
            # =================================================

            header_cols = st.columns(
                [
                    0.55,
                    1.15,
                    0.65,
                    0.70,
                    0.55,
                    0.75
                ],
                gap="small"
            )


            headers = [
                "Time",
                "Symbol",
                "LTP",
                "% Chg",
                "RVOL",
                "$ Vol"
            ]


            for i, header in enumerate(headers):

                header_cols[i].markdown(
                    f"""
                    <div class="scanner-header">
                        {header}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


            # =================================================
            # STOCK ROWS
            # =================================================

            for index, row in data.iterrows():

                row_cols = st.columns(
                    [
                        0.55,
                        1.15,
                        0.65,
                        0.70,
                        0.55,
                        0.75
                    ],
                    gap="small"
                )


                # =============================================
                # TIME
                # =============================================

                try:

                    row_time = pd.to_datetime(
                        row["Time"]
                    ).strftime("%H:%M")

                except Exception:

                    row_time = "--"


                row_cols[0].markdown(
                    f"""
                    <div class="scanner-row">
                        {row_time}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


                # =============================================
                # SYMBOL
                # =============================================

                ticker = str(
                    row["Symbol"]
                )


                symbol_area = (
                    row_cols[1].columns(
                        [0.78, 0.22],
                        gap="small"
                    )
                )


                if symbol_area[0].button(
                    ticker,
                    key=f"ticker_{ticker}_{index}",
                    use_container_width=True
                ):

                    st.session_state.selected_ticker = (
                        ticker
                    )

                    st.rerun()


                # =============================================
                # WHITE REPEAT BOX
                # =============================================

                if bool(
                    row["Repeat"]
                ):

                    symbol_area[1].markdown(
                        """
                        <div class="repeat-square">
                            ■
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


                # =============================================
                # LTP
                # =============================================

                row_cols[2].markdown(
                    f"""
                    <div class="scanner-row">
                        ${float(row["LTP"]):.2f}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


                # =============================================
                # CHANGE
                # =============================================

                change = float(
                    row["% Change"]
                )


                sign = (
                    "+"
                    if change >= 0
                    else ""
                )


                row_cols[3].markdown(
                    f"""
                    <div class="scanner-row">
                        {sign}{change:.1f}%
                    </div>
                    """,
                    unsafe_allow_html=True
                )


                # =============================================
                # RVOL
                # =============================================

                row_cols[4].markdown(
                    f"""
                    <div class="scanner-row">
                        {float(row["Rel Vol"]):.1f}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


                # =============================================
                # DOLLAR VOLUME
                # =============================================

                dollar_volume = float(
                    row["Dollar Volume"]
                )


                if dollar_volume >= 1_000_000:

                    dollar_text = (
                        f"${dollar_volume / 1_000_000:.1f}M"
                    )

                elif dollar_volume >= 1_000:

                    dollar_text = (
                        f"${dollar_volume / 1_000:.0f}K"
                    )

                else:

                    dollar_text = (
                        f"${dollar_volume:.0f}"
                    )


                row_cols[5].markdown(
                    f"""
                    <div class="scanner-row">
                        {dollar_text}
                    </div>
                    """,
                    unsafe_allow_html=True
                )


    # ========================================================
    # RIGHT — 65% TRADINGVIEW
    # ========================================================

    with right_col:

        selected = (
            st.session_state.selected_ticker
        )


        st.markdown(
            f"### TradingView — {selected}"
        )


        tradingview_chart(
            selected,
            st.session_state.settings[
                "chart_interval"
            ],
            height=700
        )


# ============================================================
# START
# ============================================================

automatic_scanner()
