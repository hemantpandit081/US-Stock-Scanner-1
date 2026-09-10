import streamlit as st
import yfinance as yf
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="US Stock Screener",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# SETTINGS
# =========================================================

AUTO_REFRESH_SECONDS = 60

# Volume is considered "near the same" when it is within
# this percentage of a previous scan volume.
VOLUME_SIMILARITY_PERCENT = 15

# Number of previous scans remembered
MAX_VOLUME_HISTORY = 20


# =========================================================
# PAGE STYLE
# =========================================================

st.markdown(
    """
    <style>

    /* Reduce page spacing */
    .block-container {
        padding-top: 0.4rem;
        padding-bottom: 0.2rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
        max-width: 100%;
    }

    /* Hide Streamlit footer */
    footer {
        visibility: hidden;
    }

    /* Compact stock buttons */
    div.stButton > button {
        width: 100%;
        min-height: 30px;
        padding: 2px 6px;
        font-size: 13px;
        text-align: left;
    }

    /* Reduce expander spacing */
    div[data-testid="stExpander"] {
        margin-bottom: 5px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# AUTO REFRESH
# =========================================================

st.markdown(
    f"""
    <meta
        http-equiv="refresh"
        content="{AUTO_REFRESH_SECONDS}"
    >
    """,
    unsafe_allow_html=True
)


# =========================================================
# SESSION STATE
# =========================================================

if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = "NVDA"


if "volume_history" not in st.session_state:
    st.session_state.volume_history = {}


if "scan_number" not in st.session_state:
    st.session_state.scan_number = 0


# =========================================================
# ACTIVE US STOCK UNIVERSE
# =========================================================

STOCKS = [

    # Mega Cap / Technology
    "AAPL", "MSFT", "NVDA", "AMD", "AVGO",
    "GOOGL", "GOOG", "META", "AMZN", "TSLA",
    "NFLX", "ORCL", "CRM", "ADBE", "INTC",
    "QCOM", "MU", "SMCI", "ARM", "PLTR",

    # Finance / Trading
    "HOOD", "SOFI", "AFRM", "UPST", "PYPL",
    "COIN", "MSTR", "IBKR", "FUTU", "NU",

    # AI
    "AI", "SOUN", "BBAI", "PATH",

    # Quantum
    "IONQ", "RGTI", "QBTS", "QUBT",

    # Crypto
    "MARA", "RIOT", "CLSK", "CIFR",
    "IREN", "BTDR", "HUT",

    # EV
    "RIVN", "LCID", "NIO", "XPEV",
    "LI", "CHPT",

    # Semiconductor
    "AMAT", "LRCX", "KLAC", "MRVL",
    "ON", "WOLF", "COHR",

    # Nuclear / Energy
    "SMR", "OKLO", "UEC", "UUUU",
    "CCJ",

    # Space
    "RKLB", "ASTS", "LUNR", "RDW",

    # Defence
    "KTOS", "LMT", "NOC",

    # Biotech / Healthcare
    "MRNA", "BNTX", "CRSP",
    "RXRX", "TEM", "HIMS",

    # Internet
    "RDDT", "SNAP", "PINS", "ROKU",
    "UBER", "LYFT", "DASH",

    # Consumer
    "WMT", "COST", "TGT",
    "NKE", "LULU", "CAVA", "CMG",

    # Banks
    "JPM", "BAC", "C",
    "WFC", "GS", "MS",

    # Industrial
    "BA", "GE", "CAT", "DE",

    # High Activity
    "GME", "AMC", "PLUG",
    "OPEN", "JOBY", "ACHR"
]


# =========================================================
# DOWNLOAD MARKET DATA
# =========================================================

@st.cache_data(ttl=45)
def get_market_data():

    results = []

    try:

        data = yf.download(
            STOCKS,
            period="10d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True
        )

        for ticker in STOCKS:

            try:

                stock_data = data[ticker].dropna()

                if len(stock_data) < 2:
                    continue


                # -----------------------------------------
                # PRICE
                # -----------------------------------------

                previous_close = float(
                    stock_data["Close"].iloc[-2]
                )

                current_price = float(
                    stock_data["Close"].iloc[-1]
                )


                # -----------------------------------------
                # VOLUME
                # -----------------------------------------

                current_volume = float(
                    stock_data["Volume"].iloc[-1]
                )


                # -----------------------------------------
                # CHANGE %
                # -----------------------------------------

                if previous_close <= 0:
                    continue

                change_percent = (
                    (
                        current_price
                        - previous_close
                    )
                    / previous_close
                ) * 100


                # -----------------------------------------
                # RELATIVE VOLUME
                #
                # Current volume compared with average
                # of previous available trading days.
                # -----------------------------------------

                previous_volumes = (
                    stock_data["Volume"]
                    .iloc[:-1]
                )

                average_volume = float(
                    previous_volumes.mean()
                )

                if average_volume > 0:

                    rvol = (
                        current_volume
                        / average_volume
                    )

                else:

                    rvol = 0


                # -----------------------------------------
                # DOLLAR VOLUME
                # Price × Volume
                # -----------------------------------------

                dollar_volume = (
                    current_price
                    * current_volume
                )


                # -----------------------------------------
                # SAVE RESULT
                # -----------------------------------------

                results.append(
                    {
                        "Ticker": ticker,

                        "Price": round(
                            current_price,
                            2
                        ),

                        "Change %": round(
                            change_percent,
                            2
                        ),

                        "Volume": int(
                            current_volume
                        ),

                        "RVOL": round(
                            rvol,
                            2
                        ),

                        "Dollar Volume": round(
                            dollar_volume,
                            0
                        )
                    }
                )

            except Exception:
                continue


    except Exception as error:

        st.error(
            f"Market data error: {error}"
        )


    return pd.DataFrame(
        results
    )


# =========================================================
# VOLUME RETURN DETECTION
# =========================================================

def check_volume_return(
    ticker,
    current_volume,
    history
):

    previous_volumes = history.get(
        ticker,
        []
    )


    # No previous scan data
    if len(previous_volumes) == 0:

        return False


    for previous_volume in previous_volumes:

        if previous_volume <= 0:
            continue


        # Calculate percentage difference
        difference_percent = abs(
            (
                current_volume
                - previous_volume
            )
            / previous_volume
        ) * 100


        # Near same volume
        if (
            difference_percent
            <= VOLUME_SIMILARITY_PERCENT
        ):

            return True


        # Current volume is higher
        if (
            current_volume
            > previous_volume
        ):

            return True


    return False


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div style="
        font-size:24px;
        font-weight:700;
        line-height:1.1;
    ">
        US STOCK SCREENER
    </div>
    """,
    unsafe_allow_html=True
)


st.caption(
    "Active US Stocks • "
    f"Auto Refresh: {AUTO_REFRESH_SECONDS}s"
)


# =========================================================
# FILTERS
# =========================================================

with st.expander(
    "⚙ Filters",
    expanded=False
):

    row1_col1, row1_col2, row1_col3 = (
        st.columns(3)
    )


    with row1_col1:

        min_price = st.number_input(
            "Minimum Price",
            min_value=0.0,
            value=1.0,
            step=0.50
        )


    with row1_col2:

        max_price = st.number_input(
            "Maximum Price",
            min_value=0.0,
            value=1000.0,
            step=10.0
        )


    with row1_col3:

        min_change = st.number_input(
            "Minimum Change %",
            value=0.0,
            step=0.50
        )


    row2_col1, row2_col2, row2_col3 = (
        st.columns(3)
    )


    with row2_col1:

        min_volume = st.number_input(
            "Minimum Volume",
            min_value=0,
            value=100000,
            step=50000
        )


    with row2_col2:

        min_rvol = st.number_input(
            "Minimum Relative Volume",
            min_value=0.0,
            value=1.0,
            step=0.10
        )


    with row2_col3:

        min_dollar_volume = st.number_input(
            "Minimum Dollar Volume",
            min_value=0.0,
            value=1000000.0,
            step=1000000.0,
            format="%.0f"
        )


    # ---------------------------------------------
    # CHART INTERVAL
    # ---------------------------------------------

    chart_interval = st.selectbox(
        "Chart Interval",
        options=[
            "1",
            "5",
            "15",
            "30",
            "60",
            "240",
            "D"
        ],
        format_func=lambda x: {
            "1": "1 Minute",
            "5": "5 Minutes",
            "15": "15 Minutes",
            "30": "30 Minutes",
            "60": "1 Hour",
            "240": "4 Hours",
            "D": "1 Day"
        }[x],
        index=1
    )


# =========================================================
# LOAD MARKET DATA
# =========================================================

with st.spinner(
    "Scanning active US stocks..."
):

    df = get_market_data()


# =========================================================
# STOP IF NO DATA
# =========================================================

if df.empty:

    st.warning(
        "No market data available."
    )

    st.stop()


# =========================================================
# UPDATE VOLUME HISTORY
# =========================================================

df["Volume Signal"] = False


for index, row in df.iterrows():

    ticker = row["Ticker"]

    current_volume = row["Volume"]


    # Check against previous scans
    volume_signal = check_volume_return(

        ticker=ticker,

        current_volume=current_volume,

        history=st.session_state.volume_history
    )


    df.at[
        index,
        "Volume Signal"
    ] = volume_signal


    # Create ticker history
    if ticker not in (
        st.session_state.volume_history
    ):

        st.session_state.volume_history[
            ticker
        ] = []


    # Add current volume
    st.session_state.volume_history[
        ticker
    ].append(
        current_volume
    )


    # Keep only recent history
    st.session_state.volume_history[
        ticker
    ] = (

        st.session_state.volume_history[
            ticker
        ][
            -MAX_VOLUME_HISTORY:
        ]

    )


st.session_state.scan_number += 1


# =========================================================
# APPLY FILTERS
# =========================================================

filtered_df = df.copy()


filtered_df = filtered_df[

    (
        filtered_df["Price"]
        >= min_price
    )

    &

    (
        filtered_df["Price"]
        <= max_price
    )

    &

    (
        filtered_df["Change %"]
        >= min_change
    )

    &

    (
        filtered_df["Volume"]
        >= min_volume
    )

    &

    (
        filtered_df["RVOL"]
        >= min_rvol
    )

    &

    (
        filtered_df["Dollar Volume"]
        >= min_dollar_volume
    )

]


# =========================================================
# SORT
# =========================================================

filtered_df = filtered_df.sort_values(

    by=[
        "Volume Signal",
        "RVOL",
        "Change %"
    ],

    ascending=[
        False,
        False,
        False
    ]

)


# =========================================================
# MAIN LAYOUT
# 65% STOCK LIST
# 35% CHART
# =========================================================

left_col, right_col = st.columns(

    [65, 35],

    gap="small"

)


# =========================================================
# LEFT SIDE
# STOCK SCANNER
# =========================================================

with left_col:


    st.markdown(
        f"### Stocks ({len(filtered_df)})"
    )


    st.caption(
        "■ = Volume returned / "
        "similar volume / higher volume"
    )


    display_df = filtered_df.head(
        50
    )


    if display_df.empty:

        st.warning(
            "No stocks match your filters."
        )


    else:

        for _, row in display_df.iterrows():


            ticker = row["Ticker"]

            price = row["Price"]

            change = row["Change %"]

            volume = row["Volume"]

            rvol = row["RVOL"]

            volume_signal = row[
                "Volume Signal"
            ]


            # -----------------------------------------
            # WHITE SOLID BOX SIGNAL
            # -----------------------------------------

            if volume_signal:

                signal = "■"

            else:

                signal = " "


            button_text = (

                f"{signal} "

                f"{ticker}  |  "

                f"${price:.2f}  |  "

                f"{change:+.2f}%  |  "

                f"RVOL {rvol:.2f}  |  "

                f"VOL {volume:,.0f}"

            )


            if st.button(

                button_text,

                key=f"stock_{ticker}",

                use_container_width=True

            ):

                st.session_state.selected_stock = (
                    ticker
                )

                st.rerun()


# =========================================================
# RIGHT SIDE
# CHART
# =========================================================

with right_col:


    selected = (
        st.session_state.selected_stock
    )


    st.markdown(
        f"### {selected}"
    )


    # =====================================================
    # TRADINGVIEW EMBED
    #
    # hidesidetoolbar=0 keeps side controls available.
    # =====================================================

    tradingview_html = f"""

    <div

        style="
            width:100%;
            height:calc(100vh - 155px);
            min-height:550px;
        "

    >

        <iframe

            src="
            https://www.tradingview.com/widgetembed/
            ?symbol={selected}
            &interval={chart_interval}
            &hidesidetoolbar=0
            &symboledit=1
            &saveimage=1
            &toolbarbg=f1f3f6
            &studies=%5B%5D
            &theme=light
            &style=1
            &withdateranges=1
            &allow_symbol_change=1
            "

            style="
                width:100%;
                height:100%;
                border:none;
            "

            frameborder="0"

            allowtransparency="true"

        >

        </iframe>

    </div>

    """


    components.html(

        tradingview_html,

        height=650

    )


# =========================================================
# STATUS BAR
# =========================================================

current_time = datetime.now().strftime(
    "%H:%M:%S"
)


st.markdown(

    f"""

    <div style="

        text-align:center;

        font-size:11px;

        color:gray;

        margin-top:2px;

    ">

        🔄 Auto ON |

        Scan #{st.session_state.scan_number} |

        Updated {current_time} |

        Scanned {len(STOCKS)} stocks |

        Results {len(filtered_df)}

    </div>

    """,

    unsafe_allow_html=True

)
