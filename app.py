import streamlit as st

from webull.core.client import ApiClient
from webull.data.data_client import DataClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan


st.set_page_config(
    page_title="Webull Test",
    layout="wide"
)

st.title("Webull Connection Test")

try:
    # Webull credentials from Streamlit Secrets
    api_client = ApiClient(
        st.secrets["WEBULL_APP_KEY"],
        st.secrets["WEBULL_APP_SECRET"],
        "us"
    )

    # Webull production endpoint
    api_client.add_endpoint(
        "us",
        "api.webull.com"
    )

    data_client = DataClient(api_client)

    st.info("Testing AAPL...")

    # Get 1-minute historical bars
    response = data_client.market_data.get_history_bar(
        "AAPL",
        Category.US_STOCK.name,
        Timespan.M1.name
    )

    if response.status_code == 200:

        st.success("✅ Webull is connected!")

        data = response.json()

        st.subheader("Real Webull AAPL Data")

        st.json(data)

    else:

        st.error(
            f"Webull returned error: {response.status_code}"
        )

        st.text(response.text)

except Exception as e:

    st.error("❌ Webull connection failed")

    st.exception(e)
