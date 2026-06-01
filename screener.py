import pandas as pd
import numpy as np

def calculate_percentage_change(df: pd.DataFrame, method: str) -> pd.DataFrame:
    """
    Calculates the percentage change based on the selected method.
    The baseline is always the oldest price point.
    Methods supported:
    - Close - Previous Close (Baseline: Previous Close)
    - Open - Close (Baseline: Open)
    - High - Low (Baseline: Low)
    - Close - Open (Next day) -> We'll use Close(today) - Open(today)
    """
    df = df.copy()
    
    if method == "Close - Previous Close":
        # Baseline is Previous Close
        # Handle cases where PREVCLOSE is 0 or NaN to avoid division by zero
        df['BASE_PRICE'] = df['PREVCLOSE']
        df['CURRENT_PRICE'] = df['CLOSE']
        
    elif method == "Open - Close":
        # Baseline is Open
        df['BASE_PRICE'] = df['OPEN']
        df['CURRENT_PRICE'] = df['CLOSE']
        
    elif method == "High - Low":
        # Baseline is Low
        df['BASE_PRICE'] = df['LOW']
        df['CURRENT_PRICE'] = df['HIGH']
        
    else:
        # Default to Close - PrevClose
        df['BASE_PRICE'] = df['PREVCLOSE']
        df['CURRENT_PRICE'] = df['CLOSE']
    
    # Calculate % change
    df['PCT_CHANGE'] = np.where(
        df['BASE_PRICE'] > 0,
        ((df['CURRENT_PRICE'] - df['BASE_PRICE']) / df['BASE_PRICE']) * 100,
        np.nan
    )
    
    return df

def apply_filters(df: pd.DataFrame, 
                  instruments: list[str], 
                  min_liquidity: float,
                  pct_cutoff: float,
                  max_pct_cutoff: float,
                  is_increase: bool,
                  min_days_pct: float) -> pd.DataFrame:
    """
    Applies the filters based on user input.
    """
    if df.empty:
        return df

    # 1. Filter by Instrument
    if "All" not in instruments and len(instruments) > 0:
        df = df[df['INSTRUMENT_TYPE'].isin(instruments)].copy()

    # 2. Calculate % change condition
    if is_increase:
        df['CONDITION_MET'] = (df['PCT_CHANGE'] >= pct_cutoff) & (df['PCT_CHANGE'] <= max_pct_cutoff)
    else:
        df['CONDITION_MET'] = (df['PCT_CHANGE'] <= -pct_cutoff) & (df['PCT_CHANGE'] >= -max_pct_cutoff)

    # 3. Apply Liquidity condition
    if min_liquidity > 0:
        df['CONDITION_MET'] = df['CONDITION_MET'] & (df['TURNOVER'] >= min_liquidity)

    # 4. Aggregation for "% of days" rule
    # We want to find symbols that meet the condition for at least `min_days_pct` of the TOTAL evaluated days.
    # If an illiquid stock didn't trade on some days, those missing days count as non-passing days.
    total_days = df['DATE'].nunique()
    met_days = df.groupby('SYMBOL')['CONDITION_MET'].transform('sum')
    
    df['MET_PCT'] = (met_days / total_days) * 100
    
    # Filter symbols that meet the % of days condition
    df = df[df['MET_PCT'] >= min_days_pct]
    
    return df

def get_latest_data_and_sort(df: pd.DataFrame, sort_by: str, top_n: int, is_increase: bool = True) -> pd.DataFrame:
    """
    Extracts the latest data for each valid symbol and sorts it.
    """
    if df.empty:
        return df
        
    # Get the latest date for each symbol
    idx = df.groupby('SYMBOL')['DATE'].idxmax()
    latest_df = df.loc[idx].copy()
    
    # Sort
    if sort_by == "% Change":
        latest_df = latest_df.sort_values(by='PCT_CHANGE', ascending=not is_increase)
    elif sort_by == "Volume":
        latest_df = latest_df.sort_values(by='VOLUME', ascending=False)
    elif sort_by == "Turnover":
        latest_df = latest_df.sort_values(by='TURNOVER', ascending=False)
    else:
        # Default fallback
        latest_df = latest_df.sort_values(by='PCT_CHANGE', ascending=not is_increase)
        
    # Apply Top N
    if top_n > 0:
        latest_df = latest_df.head(top_n)
        
    # Formatting
    latest_df = latest_df[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER', 'PCT_CHANGE', 'MET_PCT']]
    
    return latest_df
