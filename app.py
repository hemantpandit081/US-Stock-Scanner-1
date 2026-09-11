import streamlit as st
import streamlit.components.v1 as components

# ============================================================
# PAGE SETTINGS
# ============================================================

st.set_page_config(
    page_title="US Stock Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ============================================================
# SESSION STATE
# ============================================================

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "NVDA"

if "watchlist" not in st.session_state:
    st.session_state.watchlist = [
        "NVDA",
        "PLTR",
        "AMD"
    ]


# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

/* Main page */

.block-container {
    padding-top: 0.5rem;
    padding-left: 0.6rem;
    padding-right: 0.6rem;
    max-width: 100%;
}


/* Remove extra spacing */

div[data-testid="stVerticalBlock"] {
    gap: 0.35rem;
}


/* Main title */

.scanner-title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 5px;
}


/* Tab text */

button[data-baseweb="tab"] {
    font-size: 11px !important;
    font-weight: 600 !important;
    padding-left: 7px !important;
    padding-right: 7px !important;
}


/* Stock button */

.stock-button button {
    text-align: left !important;
    font-weight: 600 !important;
}


/* Scanner row */

.scan-row {
    border-bottom: 1px solid #303030;
    padding-top: 4px;
    padding-bottom: 4px;
}


/* Small information */

.small-info {
    font-size: 11px;
    color: #888;
}


/* Green */

.green {
    color: #00c853;
    font-weight: 600;
}


/* Red */

.red {
    color: #ff5252;
    font-weight: 600;
}


/* Repeat indicator */

.repeat {
    color: #00c853;
    font-size: 15px;
    font-weight: bold;
}


/* Chart */

.chart-container {
    width: 100%;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# FUNCTIONS
# ============================================================

def select_stock(symbol):

    st.session_state.selected_symbol = symbol
    st.rerun()


def add_to_watchlist(symbol):

    symbol = symbol.upper().strip()

    if symbol and symbol not in st.session_state.watchlist:
        st.session_state.watchlist.append(symbol)


def remove_from_watchlist(symbol):

    if symbol in st.session_state.watchlist:
        st.session_state.watchlist.remove(symbol)

    if (
        st.session_state.selected_symbol == symbol
        and st.session_state.watchlist
    ):
        st.session_state.selected_symbol = (
            st.session_state.watchlist[0]
        )


def tradingview_chart(symbol):

    html = f"""
    <div style="width:100%; height:720px;">
        <iframe
            src="https://www.tradingview.com/widgetembed/?
            symbol=NASDAQ%3A{symbol}
            &interval=1
            &hidesidetoolbar=0
            &symboledit=1
            &saveimage=0
            &toolbarbg=%23131313
            &theme=dark
            &style=1
            &timezone=America%2FNew_York
            &withdateranges=1
            &hideideas=1"
            style="
                width:100%;
                height:100%;
                border:none;
            ">
        </iframe>
    </div>
    """

    # Remove spaces/newlines from URL
    html = html.replace("\n", "").replace(" ", "")

    components.html(
        html,
        height=720,
        scrolling=False
    )


# ============================================================
# SAMPLE DATA
#
# This is temporary.
# Next step = replace this with Webull data.
# ============================================================

regular_stocks = [
    {
        "symbol": "NVDA",
        "price": 182.40,
        "change": 4.52,
        "rvol": 3.82,
        "volume": 8400000,
        "repeat": True
    },
    {
        "symbol": "PLTR",
        "price": 151.20,
        "change": 3.17,
        "rvol": 2.91,
        "volume": 4100000,
        "repeat": True
    },
    {
        "symbol": "AMD",
        "price": 168.30,
        "change": 2.84,
        "rvol": 2.54,
        "volume": 6700000,
        "repeat": False
    },
    {
        "symbol": "TSLA",
        "price": 348.20,
        "change": 2.31,
        "rvol": 2.20,
        "volume": 6200000,
        "repeat": False
    },
    {
        "symbol": "AAPL",
        "price": 238.10,
        "change": 1.82,
        "rvol": 1.94,
        "volume": 5100000,
        "repeat": True
    },
]


# ============================================================
# MAIN LAYOUT
# ============================================================

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT 35%
# ============================================================

with left:

    st.markdown(
        '<div class="scanner-title">US STOCK SCANNER</div>',
        unsafe_allow_html=True
    )


    # ========================================================
    # THREE MAIN TABS
    # ========================================================

    watchlist_tab, regular_tab, watchlist_scan_tab = st.tabs(
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

        st.markdown("#### WATCHLIST")

        # Add stock

        new_symbol = st.text_input(
            "Add stock",
            placeholder="Enter symbol e.g. NVDA",
            label_visibility="collapsed"
        )

        if st.button(
            "＋ Add Stock",
            use_container_width=True
        ):

            if new_symbol:

                add_to_watchlist(new_symbol)

                st.rerun()


        st.markdown("---")


        # Watchlist stocks

        if not st.session_state.watchlist:

            st.info(
                "Watchlist is empty."
            )

        else:

            for symbol in st.session_state.watchlist:

                col1, col2 = st.columns(
                    [5, 1],
                    gap="small"
                )

                with col1:

                    if st.button(
                        symbol,
                        key=f"watch_{symbol}",
                        use_container_width=True
                    ):

                        select_stock(symbol)

                with col2:

                    if st.button(
                        "×",
                        key=f"delete_{symbol}"
                    ):

                        remove_from_watchlist(symbol)

                        st.rerun()


    # ========================================================
    # REGULAR SCAN
    # ========================================================

    with regular_tab:

        st.markdown("#### REGULAR SCAN")


        # Filters

        with st.expander(
            "⚙ Filters",
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


        # Scan button

        if st.button(
            "SCAN NOW",
            type="primary",
            use_container_width=True
        ):

            st.session_state.scan_started = True


        st.markdown("---")


        # Temporary sample filtering

        filtered = []

        for stock in regular_stocks:

            if stock["price"] < min_price:
                continue

            if stock["price"] > max_price:
                continue

            if stock["volume"] < min_volume:
                continue

            if stock["rvol"] < min_rvol:
                continue

            if stock["change"] < min_change:
                continue

            filtered.append(stock)


        # Results

        if filtered:

            st.caption(
                f"{len(filtered)} stocks found"
            )

            # Header

            h1, h2, h3, h4 = st.columns(
                [2, 1.3, 1.2, 1]
            )

            h1.markdown("**STOCK**")
            h2.markdown("**CHANGE**")
            h3.markdown("**RVOL**")
            h4.markdown("**REPEAT**")


            for stock in filtered:

                symbol = stock["symbol"]

                c1, c2, c3, c4 = st.columns(
                    [2, 1.3, 1.2, 1]
                )


                with c1:

                    if st.button(
                        symbol,
                        key=f"scan_{symbol}",
                        use_container_width=True
                    ):

                        select_stock(symbol)


                with c2:

                    change = stock["change"]

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

                    st.write(
                        f'{stock["rvol"]:.2f}x'
                    )


                with c4:

                    if stock["repeat"]:

                        st.markdown(
                            '<span class="repeat">■</span>',
                            unsafe_allow_html=True
                        )

                    else:

                        st.write("")


                st.caption(
                    f'Vol: {stock["volume"]:,} '
                    f'| ${stock["price"]:.2f}'
                )


        else:

            st.info(
                "No stocks match the filters."
            )


    # ========================================================
    # WATCHLIST STOCK SCAN
    # ========================================================

    with watchlist_scan_tab:

        st.markdown(
            "#### WATCHLIST STOCK SCAN"
        )

        st.caption(
            "Only your Watchlist stocks are monitored "
            "for repeat volume."
        )


        if not st.session_state.watchlist:

            st.info(
                "Add stocks to Watchlist first."
            )

        else:

            if st.button(
                "SCAN WATCHLIST",
                type="primary",
                use_container_width=True
            ):

                st.session_state.watchlist_scan_started = True


            st.markdown("---")


            # Create results from stocks in watchlist

            for symbol in st.session_state.watchlist:

                matching = None

                for stock in regular_stocks:

                    if stock["symbol"] == symbol:

                        matching = stock
                        break


                if matching is None:

                    continue


                c1, c2, c3 = st.columns(
                    [2, 1.3, 1]
                )


                with c1:

                    if st.button(
                        symbol,
                        key=f"watchscan_{symbol}",
                        use_container_width=True
                    ):

                        select_stock(symbol)


                with c2:

                    st.write(
                        f'{matching["rvol"]:.2f}x'
                    )


                with c3:

                    if matching["repeat"]:

                        st.markdown(
                            '<span class="repeat">■</span>',
                            unsafe_allow_html=True
                        )


                st.caption(
                    f'Volume: '
                    f'{matching["volume"]:,}'
                )


# ============================================================
# RIGHT 65%
# ============================================================

with right:

    selected = st.session_state.selected_symbol


    # Header

    st.markdown(
        f"### {selected}"
    )

    st.caption(
        "NASDAQ / US Market"
    )


    # TradingView

    tradingview_chart(selected)
