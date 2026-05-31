import os
from datetime import date, timedelta
from data_fetcher import fetch_data_for_dates
from screener import calculate_percentage_change, apply_filters, get_latest_data_and_sort

def test_screener():
    # Use last Friday to be safe (if weekend)
    d = date.today() - timedelta(days=2) 
    while d.weekday() > 4:
        d -= timedelta(days=1)
        
    dates = [d]
    print(f"Fetching data for {dates}")
    df = fetch_data_for_dates(dates)
    if df.empty:
        print("DataFrame is empty, skipping further tests.")
        return
        
    print(f"Fetched {len(df)} rows.")
    
    df = calculate_percentage_change(df, "Close - Previous Close")
    
    filtered_df = apply_filters(
        df=df,
        instrument="Equity",
        min_liquidity=10000000,
        pct_cutoff=5.0,
        max_pct_cutoff=100.0,
        is_increase=True,
        min_days_pct=100
    )
    
    print(f"Filtered {len(filtered_df)} rows.")
    
    final_df = get_latest_data_and_sort(filtered_df, "% Change", 5)
    print("Top 5 results:")
    print(final_df[['SYMBOL', 'PCT_CHANGE', 'TURNOVER']])

if __name__ == "__main__":
    test_screener()
