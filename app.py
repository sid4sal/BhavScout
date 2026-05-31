import streamlit as st
import pandas as pd
from datetime import date, timedelta
from data_fetcher import fetch_data_for_dates
from screener import calculate_percentage_change, apply_filters, get_latest_data_and_sort

st.set_page_config(page_title="Indian Stock Screener", layout="wide")

st.title("📈 Indian Stock Screener")

with st.expander("⚙️ Filters & Settings", expanded=True):
    market = st.selectbox("Market", ["Both", "NSE", "BSE"], help="Select the stock exchange(s) to scan.")
    instrument = st.selectbox("Instrument", ["All", "Equity", "Futures", "Options"], help="Filter by Equity (stocks) or derivatives. Example: 'Equity' for normal stocks.")
    time_frame = st.selectbox("Timeframe", ["Last N days", "Date Range", "Specific Date", "Today", "Yesterday"], help="Select the date range to fetch market data for. Example: 'Last N days' checks recent history.")

    dates_to_fetch = []
    today = date.today()

    if time_frame == "Today":
        dates_to_fetch = [today]
    elif time_frame == "Yesterday":
        # If today is Monday, yesterday is Friday
        offset = 3 if today.weekday() == 0 else (2 if today.weekday() == 6 else 1)
        dates_to_fetch = [today - timedelta(days=offset)]
    elif time_frame == "Last N days":
        n_days = st.number_input("N Days", min_value=1, max_value=30, value=5)
        # Get last N weekdays
        d = today
        while len(dates_to_fetch) < n_days:
            if d.weekday() < 5: # Monday to Friday
                dates_to_fetch.append(d)
            d -= timedelta(days=1)
    elif time_frame == "Specific Date":
        selected_date = st.date_input("Select Date", value=today)
        dates_to_fetch = [selected_date]
    elif time_frame == "Date Range":
        date_range = st.date_input("Select Date Range", value=(today - timedelta(days=7), today))
        if len(date_range) == 2:
            start_date, end_date = date_range
            # Generate weekdays between start and end
            current_date = start_date
            while current_date <= end_date:
                if current_date.weekday() < 5:
                    dates_to_fetch.append(current_date)
                current_date += timedelta(days=1)

    st.markdown("---")
    st.subheader("Filters")
    
    calc_method = st.selectbox("Base Price", ["Close - Previous Close", "Open - Close", "High - Low"], help="Method to calculate % change. Example: 'Close - Previous Close' measures from yesterday's close to today's close.")
    pct_cutoff = st.number_input("Min % Change", min_value=0.0, value=4.95, step=0.5, help="Minimum required percentage change. Example: 2.0 for a 2% move.")
    max_pct_cutoff = st.number_input("Max % Change", min_value=0.0, value=5.0, step=0.5, help="Maximum allowed percentage change. Filters out stocks moving more than this value.")
    direction_ui = st.radio("Direction", ["Up", "Down"], help="Filter for price increases (Up) or decreases (Down).")
    is_increase = direction_ui == "Up"
    
    min_days_pct = st.slider("Consistency (%)", min_value=0, max_value=100, value=100, step=10, help="Percentage of traded days the stock must meet the Min % Change. Example: 100% means it must meet it every single trading day.")
    
    min_liquidity = st.number_input("Min Turnover (₹)", min_value=0, value=0, step=1000000, help="Minimum daily trading turnover required. Example: 1000000 = 10 lakhs.")
    
    st.markdown("---")
    st.subheader("Sort & Display")
    
    sort_by = st.selectbox("Sort By", ["% Change", "Volume", "Turnover"], help="Metric to sort the final results by.")
    top_n = st.number_input("Top N Results", min_value=0, value=0, help="Number of results to display. Use 0 to show all matches.")
    
    run_screener = st.button("Run Screener", type="primary")

if run_screener:
    if not dates_to_fetch:
        st.error("Please select a valid date range.")
    else:
        with st.spinner("Fetching data and applying filters... This may take a moment if downloading fresh data."):
            # 1. Fetch Data
            df = fetch_data_for_dates(dates_to_fetch, market=market)
            
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
                    max_pct_cutoff=max_pct_cutoff,
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
                    
                    # Extract dates for summary
                    evaluated_dates = df['DATE'].dt.strftime('%Y-%m-%d').unique().tolist()
                    evaluated_dates.sort()
                    requested_dates = [d.strftime('%Y-%m-%d') for d in dates_to_fetch]
                    skipped_dates = list(set(requested_dates) - set(evaluated_dates))
                    
                    with st.expander("📊 Scan Summary", expanded=True):
                        st.markdown(f"**Dates Requested:** {len(requested_dates)} days")
                        st.markdown(f"**Trading Days Evaluated:** {len(evaluated_dates)} days ({', '.join(evaluated_dates)})")
                        if skipped_dates:
                            st.markdown(f"**Skipped (Holidays/No Data):** {len(skipped_dates)} days ({', '.join(skipped_dates)})")
                        st.markdown(f"**Filter:** {direction_ui} {pct_cutoff}% to {max_pct_cutoff}% | Consistency: {min_days_pct}% | Turnover >= ₹{min_liquidity/10000000}Cr")
                        st.markdown(f"**Sorted By:** {sort_by} (Top {'All' if top_n == 0 else top_n})")
                    
                    # Format output for better display
                    display_df = final_df.copy()
                    display_df['DATE'] = display_df['DATE'].dt.strftime('%Y-%m-%d')
                    display_df['PCT_CHANGE'] = display_df['PCT_CHANGE'].round(2).astype(str) + '%'
                    display_df['MET_PCT'] = display_df['MET_PCT'].round(0).astype(str) + '%'
                    # Format turnover to Crores for readability
                    display_df['TURNOVER (Cr)'] = (display_df['TURNOVER'] / 10000000).round(2)
                    display_df = display_df.drop(columns=['TURNOVER'])
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
