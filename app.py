# %% import stuff
import datetime
import sys

import pandas as pd
import plotly.express as px
import streamlit as st
from shroomdk import ShroomDK

# %% get params
st.set_page_config(
    page_title="swaps visualizer",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="collapsed",
    # menu_items={'About': "something"}
)

st.write("# swaps visualizer")


st.info(
    "this tool is only available on Ethereum, and it covers Uniswap, Sushiswap, Balancer and Curve swaps"
)

token_a = st.text_input("symbol or address of the token A", "USDC")
token_b = st.text_input("symbol or address of the token B", "WETH")

type_a = "token" if len(token_a) == 42 else "symbol"
type_b = "token" if len(token_b) == 42 else "symbol"

number_of_trades = st.number_input(
    "number of trades to show", value=10_000, min_value=1, max_value=100_000
)

checkbox_col1, checkbox_col2, checkbox_col3 = st.columns(3)
should_filter_by_date = checkbox_col1.checkbox("filter by date")
should_show_raw_data = checkbox_col2.checkbox("show raw data")
should_show_scatter_plot = checkbox_col3.checkbox("show scatter plot")


if should_filter_by_date:
    date_col1, date_col2 = st.columns(2)
    start_date = date_col1.date_input("start date", value=None)
    end_date = date_col2.date_input("end date", value=None)

# %% create query
time_filter = (
    f"""and block_timestamp between '{start_date.strftime("%Y-%m-%d")}' and '{end_date.strftime("%Y-%m-%d")}'"""
    if should_filter_by_date
    else ""
)

swaps_query = f"""
SELECT 
  *,
  'token_a_in' as side
FROM ethereum.core.ez_dex_swaps 
WHERE 1=1
  and lower({type_a}_in)=lower('{token_a}') and lower({type_b}_out)=lower('{token_b}')
  {time_filter}

UNION ALL

SELECT 
  *,
  'token_a_out' as side
FROM ethereum.core.ez_dex_swaps 
WHERE 1=1
  and lower({type_a}_out)=lower('{token_a}') and lower({type_b}_in)=lower('{token_b}')
  {time_filter}

ORDER BY block_timestamp DESC

LIMIT {number_of_trades}
"""

# %% get data
@st.cache(ttl=15)
def get_data(query):
    # Initialize `ShroomDK` with your API Key
    sdk = ShroomDK(st.secrets['SHROOM_DK_KEY'])

    query_result_set = sdk.query(query)
    df = pd.DataFrame(query_result_set.rows, columns=query_result_set.columns)
    return df


if should_show_raw_data or should_show_scatter_plot:
    swaps = get_data(swaps_query).copy()

    if len(swaps) == 0:
        st.error("no data found, check the parameters")
        st.stop()

    # %% initial processing
    swaps["BLOCK_TIMESTAMP"] = pd.to_datetime(swaps["BLOCK_TIMESTAMP"])
    swaps["SIDE"] = swaps["SIDE"].apply(
        lambda x: "token_a_sell" if x == "token_a_in" else "token_a_buy"
    )

    swaps["AMOUNT_TOKEN_A"] = swaps.apply(
        lambda x: x["AMOUNT_IN"] if x["SIDE"] == "token_a_sell" else x["AMOUNT_OUT"],
        axis=1,
    )
    swaps["AMOUNT_TOKEN_B"] = swaps.apply(
        lambda x: x["AMOUNT_OUT"] if x["SIDE"] == "token_a_sell" else x["AMOUNT_IN"],
        axis=1,
    )
    swaps["SYMBOL_TOKEN_A"] = swaps.apply(
        lambda x: x["SYMBOL_IN"] if x["SIDE"] == "token_a_sell" else x["SYMBOL_OUT"],
        axis=1,
    )
    swaps["SYMBOL_TOKEN_B"] = swaps.apply(
        lambda x: x["SYMBOL_OUT"] if x["SIDE"] == "token_a_sell" else x["SYMBOL_IN"],
        axis=1,
    )

    swaps["PRICE_TOKEN_A_TO_TOKEN_B"] = (
        swaps["AMOUNT_TOKEN_A"] / swaps["AMOUNT_TOKEN_B"]
    )

# %% show raw data
if should_show_raw_data:
    st.write("## raw data")
    st.write(swaps)

    swaps_csv = st.cache(lambda _: swaps.to_csv().encode("utf-8"))(None)
    st.download_button(
        label="Download raw swaps data as CSV",
        data=swaps_csv,
        file_name="large_df.csv",
        mime="text/csv",
    )

# %% show scatter plot
if should_show_scatter_plot:
    st.write("## scatter plot")
    
    height = st.number_input(
        "height of the plot", value=800, min_value=100, max_value=10000
    )
    
    should_breakdown_by_platform = st.checkbox("breakdown by platform")
    
    filter_platform = st.multiselect("filter by platform", swaps["PLATFORM"].unique(), default=swaps["PLATFORM"].unique())

    tmp = swaps[swaps["PLATFORM"].isin(filter_platform)]

    fig = px.scatter(
        tmp,
        x="BLOCK_TIMESTAMP",
        y="PRICE_TOKEN_A_TO_TOKEN_B",
        color="SIDE",
        opacity=0.5,
        size="AMOUNT_IN_USD",
        height=800,
        hover_data=[
            "PLATFORM",
            "ORIGIN_FROM_ADDRESS",
            "POOL_NAME",
            "AMOUNT_TOKEN_A",
            "AMOUNT_TOKEN_B",
            "SIDE",
        ],
        facet_row='PLATFORM' if should_breakdown_by_platform else None,
        title=f"<b>swaps between {token_a} (token A) and {token_b} (token B)</b>"
        "<br>dot size = usd size of the swap",
    )

    # fig.update_yaxes(matches=None)

    st.plotly_chart(fig, use_container_width=True)
