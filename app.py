import streamlit as st
import pandas as pd
from datetime import date, timedelta
from data_fetcher import fetch_data_for_dates
from screener import calculate_percentage_change, apply_filters, get_latest_data_and_sort

st.set_page_config(page_title="Indian Stock Screener", layout="wide")

st.title("📈 Indian Stock Screener")

# Sidebar for Filters
st.sidebar.header("Filters & Settings")

market = st.sidebar.selectbox("Market", ["NSE"]) # Only NSE supported for now

instrument = st.sidebar.selectbox(
    "Instrument Type", 
    ["All", "Equity", "Futures", "Options"]
)

time_frame = st.sidebar.selectbox(
    "Time Frame",
    ["Today", "Yesterday", "Last N days", "Specific Date", "Date Range"]
)

dates_to_fetch = []
today = date.today()

if time_frame == "Today":
    dates_to_fetch = [today]
elif time_frame == "Yesterday":
    # If today is Monday, yesterday is Friday
    offset = 3 if today.weekday() == 0 else (2 if today.weekday() == 6 else 1)
    dates_to_fetch = [today - timedelta(days=offset)]
elif time_frame == "Last N days":
    n_days = st.sidebar.number_input("N Days", min_value=1, max_value=30, value=5)
    # Get last N weekdays
    d = today
    while len(dates_to_fetch) < n_days:
        if d.weekday() < 5: # Monday to Friday
            dates_to_fetch.append(d)
        d -= timedelta(days=1)
elif time_frame == "Specific Date":
    selected_date = st.sidebar.date_input("Select Date", value=today)
    dates_to_fetch = [selected_date]
elif time_frame == "Date Range":
    date_range = st.sidebar.date_input("Select Date Range", value=(today - timedelta(days=7), today))
    if len(date_range) == 2:
        start_date, end_date = date_range
        # Generate weekdays between start and end
        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5:
                dates_to_fetch.append(current_date)
            current_date += timedelta(days=1)

st.sidebar.markdown("---")
st.sidebar.subheader("Filter Conditions")

calc_method = st.sidebar.selectbox(
    "Calculation Method",
    ["Close - Previous Close", "Open - Close", "High - Low"]
)

pct_cutoff = st.sidebar.number_input("% Cutoff", min_value=0.0, value=2.0, step=0.5)
direction = st.sidebar.radio("Direction", ["Increase", "Decrease"])
is_increase = direction == "Increase"

min_days_pct = st.sidebar.slider("Condition met for at least X% of days", min_value=0, max_value=100, value=100, step=10)

min_liquidity = st.sidebar.number_input("Minimum Liquidity (Turnover in Rs)", min_value=0, value=10000000, step=1000000, help="E.g. 10000000 = 1 Crore")

st.sidebar.markdown("---")
st.sidebar.subheader("Sorting & Display")

sort_by = st.sidebar.selectbox(
    "Sort By",
    ["% Change (Latest Date)", "Volume", "Liquidity (Turnover)"]
)

top_n = st.sidebar.number_input("Display Top N Results (0 for all)", min_value=0, value=20)

if st.sidebar.button("Run Screener", type="primary"):
    if not dates_to_fetch:
        st.error("Please select a valid date range.")
    else:
        with st.spinner("Fetching data and applying filters... This may take a moment if downloading fresh data."):
            # 1. Fetch Data
            df = fetch_data_for_dates(dates_to_fetch)
            
            if df.empty:
                st.warning("No data found for the selected dates. Please try different dates (weekends/holidays have no data).")
            else:
                # 2. Calculate Percentage Changes
                df = calculate_percentage_change(df, calc_method)
                
                # 3. Apply Filters
                filtered_df = apply_filters(
                    df=df,
                    instrument=instrument,
                    min_liquidity=min_liquidity,
                    pct_cutoff=pct_cutoff,
                    is_increase=is_increase,
                    min_days_pct=min_days_pct
                )
                
                # 4. Get Latest Data & Sort
                final_df = get_latest_data_and_sort(
                    df=filtered_df,
                    sort_by=sort_by,
                    top_n=top_n
                )
                
                if final_df.empty:
                    st.info("No stocks matched your criteria.")
                else:
                    st.success(f"Found {len(final_df)} matching stocks.")
                    
                    # Format output for better display
                    display_df = final_df.copy()
                    display_df['DATE'] = display_df['DATE'].dt.strftime('%Y-%m-%d')
                    display_df['PCT_CHANGE'] = display_df['PCT_CHANGE'].round(2).astype(str) + '%'
                    display_df['MET_PCT'] = display_df['MET_PCT'].round(0).astype(str) + '%'
                    # Format turnover to Crores for readability
                    display_df['TURNOVER (Cr)'] = (display_df['TURNOVER'] / 10000000).round(2)
                    display_df = display_df.drop(columns=['TURNOVER'])
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
