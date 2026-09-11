import streamlit as st

st.set_page_config(
    page_title="US Stock Scanner",
    layout="wide"
)

# -----------------------------
# CSS
# -----------------------------
st.markdown("""
<style>

.block-container {
    padding-top: 1rem;
    padding-left: 1rem;
    padding-right: 1rem;
}

/* Left panel */
.left-panel {
    width: 100%;
}

/* Stock rows */
.stock-row {
    padding: 8px;
    border-bottom: 1px solid #333;
}

</style>
""", unsafe_allow_html=True)


# -----------------------------
# PAGE TITLE
# -----------------------------

st.title("US Stock Scanner")


# -----------------------------
# 35% / 65% LAYOUT
# -----------------------------

left, right = st.columns(
    [35, 65],
    gap="small"
)


# ============================================================
# LEFT SIDE
# ============================================================

with left:

    # IMPORTANT:
    # These are the three navigation tabs.
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

        st.subheader("Watchlist")

        st.write("Your saved stocks will appear here.")

        st.button("AAPL", use_container_width=True)
        st.button("NVDA", use_container_width=True)
        st.button("PLTR", use_container_width=True)


    # ========================================================
    # REGULAR SCAN
    # ========================================================

    with regular_tab:

        st.subheader("Regular Scan")

        st.write("US market scanner will appear here.")

        st.button(
            "SCAN NOW",
            use_container_width=True
        )


    # ========================================================
    # WATCHLIST STOCK SCAN
    # ========================================================

    with watchlist_scan_tab:

        st.subheader("Watchlist Stock Scan")

        st.write(
            "Repeat-volume scanner for Watchlist stocks "
            "will appear here."
        )

        st.button(
            "SCAN WATCHLIST",
            use_container_width=True
        )


# ============================================================
# RIGHT SIDE
# ============================================================

with right:

    st.subheader("TradingView")

    st.info(
        "TradingView chart will be connected here."
    )

    st.write(
        "65% chart area"
    )
