import pandas as pd
import numpy as np
from stock_classifier import add_classifications, load_market_cap_data

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
    
    # Ensure columns are numeric to prevent comparison errors
    df['BASE_PRICE'] = pd.to_numeric(df['BASE_PRICE'], errors='coerce')
    df['CURRENT_PRICE'] = pd.to_numeric(df['CURRENT_PRICE'], errors='coerce')

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

    df = df.copy()

    # Calculate total dates available per exchange before filtering instruments
    if 'EXCHANGE' in df.columns:
        exchange_days = df.groupby('EXCHANGE')['DATE'].nunique()
    else:
        # Fallback if EXCHANGE is not present for some reason
        exchange_days = {None: df['DATE'].nunique()}

    # 1. Filter by Instrument
    if "All" not in instruments and len(instruments) > 0:
        df = df[df['INSTRUMENT_TYPE'].isin(instruments)]

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
    if 'EXCHANGE' in df.columns:
        total_days = df['EXCHANGE'].map(exchange_days)
    else:
        total_days = exchange_days[None]
        
    met_days = df.groupby('SYMBOL')['CONDITION_MET'].transform('sum')
    
    df['MET_PCT'] = (met_days / total_days) * 100
    
    # Filter symbols that meet the % of days condition
    df = df[df['MET_PCT'] >= min_days_pct]
    
    return df

def get_latest_data_and_sort(df: pd.DataFrame, sort_by: str, top_n: int, is_increase: bool = True, mcap_data: dict = None) -> pd.DataFrame:
    """
    Extracts the latest data for each valid symbol, adds classification columns, and sorts it.
    """
    if df.empty:
        return df
        
    # Get the latest date for each symbol
    idx = df.groupby('SYMBOL')['DATE'].idxmax()
    latest_df = df.loc[idx].copy()
    
    # Add classification columns (CATEGORY, SETTLEMENT, RESTRICTIONS, IS_SME, MARKET_CAP)
    if 'SERIES' in latest_df.columns and 'EXCHANGE' in latest_df.columns:
        latest_df = add_classifications(latest_df, mcap_data)
    
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
        
    # Build output columns — include classification columns if present
    base_cols = ['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER', 'PCT_CHANGE', 'MET_PCT']
    classification_cols = ['CATEGORY', 'SETTLEMENT', 'RESTRICTIONS', 'IS_SME', 'MARKET_CAP']
    output_cols = base_cols + [c for c in classification_cols if c in latest_df.columns]
    latest_df = latest_df[output_cols]
    
    return latest_df


def filter_by_category(df: pd.DataFrame, categories: list[str] = None, market_caps: list[str] = None) -> pd.DataFrame:
    """
    Filter stocks by category, market cap, and SME status.
    Applied after classification columns are added.
    
    Args:
        df: DataFrame with classification columns.
        categories: List of categories to include, e.g. ['Normal', 'T2T', 'SME'].
                   If None or contains 'All', no category filtering is applied.
        market_caps: List of market caps to include, e.g. ['Large Cap', 'Mid Cap'].
                    If None or contains 'All', no market cap filtering is applied.
    
    Returns:
        Filtered DataFrame.
    """
    if df.empty:
        return df
    
    df = df.copy()
    
    if categories and 'All' not in categories and 'CATEGORY' in df.columns:
        # Map user-friendly filter names to internal category values
        cat_map = {
            'Normal': ['Normal'],
            'T2T': ['T2T'],
            'SME': ['SME', 'SME (T2T)', 'SME (Odd Lot)'],
            'Non-compliant': ['Non-compliant'],
            'Suspended': ['Suspended'],
            'Other': ['Other', 'Block Deal', 'Book Transfer', 'Illiquid', 'Institutional'],
        }
        allowed = []
        for cat in categories:
            allowed.extend(cat_map.get(cat, [cat]))
        df = df[df['CATEGORY'].isin(allowed)]
    
    if market_caps and 'All' not in market_caps and 'MARKET_CAP' in df.columns:
        df = df[df['MARKET_CAP'].isin(market_caps)]
    
    return df
