import streamlit as st
import pandas as pd
from datetime import date, timedelta
from data_fetcher import fetch_data_for_dates
from screener import calculate_percentage_change, apply_filters, get_latest_data_and_sort, filter_by_category
from stock_classifier import load_market_cap_data

st.set_page_config(page_title="Indian Stock Screener", layout="wide")

st.title("📈 Indian Stock Screener")

with st.expander("⚙️ Filters & Settings", expanded=True):
    market = st.multiselect("Market", ["NSE", "BSE"], default=["NSE", "BSE"], help="Select the stock exchange(s) to scan.")
    instrument = st.multiselect("Instrument", ["All", "Equity", "Futures", "Options", "ETF", "Index"], default=["Equity"], help="Filter by Equity (stocks), derivatives, ETFs, or Indices.")
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
    st.subheader("Stock Category")
    
    stock_category = st.multiselect(
        "Category Filter",
        ["All", "Normal", "T2T", "SME", "Non-compliant"],
        default=["All"],
        help="Filter by stock category. Normal = regular equity, T2T = trade-to-trade (delivery only, no intraday), SME = Small & Medium Enterprise stocks."
    )
    
    market_cap_filter = st.multiselect(
        "Market Cap",
        ["All", "Large Cap", "Mid Cap", "Small Cap"],
        default=["All"],
        help="Filter by AMFI market cap classification. Large Cap = Top 100, Mid Cap = 101-250, Small Cap = 251+ by full market capitalization."
    )
    
    st.markdown("---")
    st.subheader("Sort & Display")
    
    sort_by = st.selectbox("Sort By", ["Turnover", "% Change", "Volume"], help="Metric to sort the final results by.")
    top_n = st.number_input("Top N Results", min_value=0, value=0, help="Number of results to display. Use 0 to show all matches.")
    
    run_screener = st.button("Run Screener", type="primary")

if run_screener:
    if not dates_to_fetch:
        st.error("Please select a valid date range.")
    else:
        with st.spinner("Fetching data and applying filters... This may take a moment if downloading fresh data."):
            # 0. Load market cap data (cached)
            mcap_data = load_market_cap_data()
            
            # 1. Fetch Data
            df = fetch_data_for_dates(dates_to_fetch, markets=market)
            
            if df.empty:
                st.warning("No data found for the selected dates. Please try different dates (weekends/holidays have no data).")
            else:
                # 2. Calculate Percentage Changes
                df = calculate_percentage_change(df, calc_method)
                
                # 3. Apply Filters
                filtered_df = apply_filters(
                    df=df,
                    instruments=instrument,
                    min_liquidity=min_liquidity,
                    pct_cutoff=pct_cutoff,
                    max_pct_cutoff=max_pct_cutoff,
                    is_increase=is_increase,
                    min_days_pct=min_days_pct
                )
                
                # 4. Get Latest Data, Add Classifications & Sort
                final_df = get_latest_data_and_sort(
                    df=filtered_df,
                    sort_by=sort_by,
                    top_n=top_n,
                    is_increase=is_increase,
                    mcap_data=mcap_data
                )
                
                # 5. Apply Category & Market Cap Filters
                final_df = filter_by_category(
                    df=final_df,
                    categories=stock_category,
                    market_caps=market_cap_filter
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
                        
                        # Category legend
                        st.markdown("---")
                        st.markdown("**📋 Category Legend:**")
                        legend_cols = st.columns(4)
                        with legend_cols[0]:
                            st.markdown("🟢 **Normal** — Standard equity, intraday allowed")
                        with legend_cols[1]:
                            st.markdown("🔒 **T2T** — Trade-to-Trade, delivery only (No Intraday). T2T impose a T+1 Settlement restriction and disables Buy Today, Sell Tomorrow (BTST). Which means the stock can only be sold on/after T+1 day, depending on the exact settlement time.")
                        with legend_cols[2]:
                            st.markdown("🏢 **SME** — SME/Emerge platform, T+2 settlement. These have a minimum lot size. Can be sold on/after T+2, depending on the exact settlement time.")
                        with legend_cols[3]:
                            st.markdown("⚠️ **Non-compliant** — SEBI non-compliant")
                    
                    # Format output for better display
                    display_df = final_df.copy()
                    display_df['DATE'] = display_df['DATE'].dt.strftime('%Y-%m-%d')
                    display_df['PCT_CHANGE'] = display_df['PCT_CHANGE'].round(2).astype(str) + '%'
                    display_df['MET_PCT'] = display_df['MET_PCT'].round(0).astype(str) + '%'
                    # Format turnover to Crores for readability
                    display_df['TURNOVER (Cr)'] = (display_df['TURNOVER'] / 10000000).round(2)
                    display_df = display_df.drop(columns=['TURNOVER'])
                    
                    # Format IS_SME as emoji
                    if 'IS_SME' in display_df.columns:
                        display_df['IS_SME'] = display_df['IS_SME'].apply(lambda x: '✅' if x else '—')
                    
                    # Add category emoji prefix for visual clarity
                    if 'CATEGORY' in display_df.columns:
                        cat_emoji = {
                            'Normal': '🟢',
                            'T2T': '🔒',
                            'SME': '🏢',
                            'SME (T2T)': '🏢🔒',
                            'SME (Odd Lot)': '🏢',
                            'Non-compliant': '⚠️',
                            'Suspended': '🚫',
                            'Other': '⚪',
                        }
                        display_df['CATEGORY'] = display_df['CATEGORY'].apply(
                            lambda x: f"{cat_emoji.get(x, '⚪')} {x}"
                        )
                    
                    # Add settlement emoji
                    if 'SETTLEMENT' in display_df.columns:
                        settle_emoji = {
                            'T+1': '✅',
                            'T+1 (T2T)': '🔒',
                            'T+2': '⏳',
                            'T+2 (T2T)': '⏳🔒',
                            'N/A': '🚫',
                        }
                        display_df['SETTLEMENT'] = display_df['SETTLEMENT'].apply(
                            lambda x: f"{settle_emoji.get(x, '')} {x}"
                        )
                    # Reorder columns for display
                    cols = display_df.columns.tolist()
                    front_cols = ['SYMBOL', 'INSTRUMENT_TYPE', 'CATEGORY', 'SETTLEMENT', 'TURNOVER (Cr)']
                    front_cols = [c for c in front_cols if c in cols]
                    remaining_cols = [c for c in cols if c not in front_cols]
                    display_df = display_df[front_cols + remaining_cols]
                    
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
