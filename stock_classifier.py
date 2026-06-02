"""
Stock Classifier Module
-----------------------
Classifies Indian stocks by:
- Trading category (Normal, T2T, SME, Non-compliant, Suspended)
- Settlement cycle (T+1, T+2, T+1 T2T, T+2 T2T)
- Restrictions (No Intraday, Locked 2 Days, etc.)
- Market cap (Large Cap, Mid Cap, Small Cap) via AMFI data
"""

import os
import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
AMFI_CACHE_FILE = os.path.join(CACHE_DIR, "amfi_mcap.csv")
AMFI_CACHE_MAX_AGE_DAYS = 30

# ─────────────────────────────────────────────
# NSE Series → Category Mapping
# ─────────────────────────────────────────────
NSE_SERIES_CATEGORY = {
    'EQ': 'Normal',
    'BE': 'T2T',
    'BZ': 'Non-compliant',
    'BL': 'Block Deal',
    'BT': 'Book Transfer',
    'SM': 'SME',
    'ST': 'SME (T2T)',
    'SO': 'SME (Odd Lot)',
    'IL': 'Illiquid',
    'IV': 'Institutional',
}

# ─────────────────────────────────────────────
# BSE Group → Category Mapping
# ─────────────────────────────────────────────
BSE_GROUP_CATEGORY = {
    'A':  'Normal',
    'B':  'Normal',
    'T':  'T2T',
    'XT': 'T2T',
    'X':  'Normal',
    'M':  'SME',
    'MT': 'SME (T2T)',
    'MS': 'SME',
    'Z':  'Suspended',
    'ZP': 'Suspended',
    'E':  'Normal',
    'F':  'Normal',
    'G':  'Normal',
    'IF': 'Normal',
    'P':  'Normal',
    'R':  'Normal',
}

# ─────────────────────────────────────────────
# Settlement cycle mappings
# ─────────────────────────────────────────────
_SETTLEMENT_MAP = {
    'Normal':        'T+1',
    'T2T':           'T+1 (T2T)',
    'SME':           'T+2',
    'SME (T2T)':     'T+2 (T2T)',
    'SME (Odd Lot)': 'T+2',
    'Non-compliant': 'T+1 (T2T)',
    'Suspended':     'N/A',
    'Block Deal':    'T+1',
    'Book Transfer': 'T+1',
    'Illiquid':      'T+1 (T2T)',
    'Institutional': 'T+1',
}


def classify_series(series_code: str, exchange: str) -> str:
    """
    Map a series/group code to a human-readable category.

    Args:
        series_code: The SctySrs value (NSE) or group code (BSE).
        exchange: 'NSE' or 'BSE'.

    Returns:
        Category string like 'Normal', 'T2T', 'SME', etc.
    """
    code = str(series_code).strip().upper()
    if exchange == 'NSE':
        return NSE_SERIES_CATEGORY.get(code, 'Other')
    elif exchange == 'BSE':
        return BSE_GROUP_CATEGORY.get(code, 'Other')
    return 'Other'


def get_settlement_info(category: str) -> str:
    """
    Return the settlement cycle string for a given category.

    Args:
        category: Output of classify_series().

    Returns:
        Settlement string like 'T+1', 'T+2', 'T+1 (T2T)', etc.
    """
    return _SETTLEMENT_MAP.get(category, 'T+1')


def is_sme(series_code: str, exchange: str) -> bool:
    """
    Check if a stock is an SME stock based on its series/group code.

    Args:
        series_code: The SctySrs value (NSE) or group code (BSE).
        exchange: 'NSE' or 'BSE'.

    Returns:
        True if the stock is an SME stock.
    """
    code = str(series_code).strip().upper()
    if exchange == 'NSE':
        return code in ('SM', 'ST', 'SO')
    elif exchange == 'BSE':
        return code in ('M', 'MT', 'MS')
    return False


def get_restrictions(category: str) -> str:
    """
    Return a comma-separated string of restrictions for a category.

    Args:
        category: Output of classify_series().

    Returns:
        Restriction string, e.g. 'No Intraday, Delivery Only' or '—' for none.
    """
    restrictions = []

    if 'T2T' in category:
        restrictions.append('No Intraday')
        restrictions.append('Delivery Only')

    if 'SME' in category:
        restrictions.append('SME Stock')
        restrictions.append('Min Lot Size')

    if category == 'Non-compliant':
        restrictions.append('Non-compliant')
        restrictions.append('No Intraday')

    if category == 'Suspended':
        restrictions.append('Suspended')

    if category == 'Illiquid':
        restrictions.append('Illiquid')
        restrictions.append('No Intraday')

    return ', '.join(restrictions) if restrictions else '—'


# ─────────────────────────────────────────────
# AMFI Market Cap Classification
# ─────────────────────────────────────────────

def load_market_cap_data() -> dict:
    """
    Load market cap classification data.
    Uses NIFTY 100 for Large Cap and NIFTY MIDCAP 150 for Mid Cap.
    Tries cached file first, downloads fresh if stale or missing.

    Returns:
        Dict mapping ISIN → 'Large Cap' / 'Mid Cap' / 'Small Cap'
    """
    mcap_data = {}
    import requests
    import io

    # Check if cached file exists and is fresh
    if os.path.exists(AMFI_CACHE_FILE):
        try:
            mtime = os.path.getmtime(AMFI_CACHE_FILE)
            age_days = (datetime.now().timestamp() - mtime) / 86400
            df = pd.read_csv(AMFI_CACHE_FILE)
            if 'ISIN' in df.columns and 'CAP_TYPE' in df.columns:
                mcap_data = dict(zip(df['ISIN'], df['CAP_TYPE']))
                if age_days <= AMFI_CACHE_MAX_AGE_DAYS:
                    logger.info(f"Loaded {len(mcap_data)} market cap entries from cache (age: {age_days:.0f} days)")
                    return mcap_data
                else:
                    logger.info(f"Market cap cache is {age_days:.0f} days old, will try to refresh")
        except Exception as e:
            logger.warning(f"Error reading market cap cache: {e}")

    # Try downloading fresh data from niftyindices
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        # NIFTY 100 -> Large Cap
        resp_large = requests.get('https://niftyindices.com/IndexConstituent/ind_nifty100list.csv', headers=headers, timeout=15)
        if resp_large.status_code == 200:
            df_large = pd.read_csv(io.StringIO(resp_large.text))
            if 'ISIN Code' in df_large.columns:
                for isin in df_large['ISIN Code'].dropna():
                    mcap_data[str(isin).strip()] = 'Large Cap'

        # NIFTY MIDCAP 150 -> Mid Cap
        resp_mid = requests.get('https://niftyindices.com/IndexConstituent/ind_niftymidcap150list.csv', headers=headers, timeout=15)
        if resp_mid.status_code == 200:
            df_mid = pd.read_csv(io.StringIO(resp_mid.text))
            if 'ISIN Code' in df_mid.columns:
                for isin in df_mid['ISIN Code'].dropna():
                    mcap_data[str(isin).strip()] = 'Mid Cap'

        if mcap_data:
            # Save to cache
            try:
                cache_df = pd.DataFrame([
                    {'ISIN': isin, 'CAP_TYPE': cap}
                    for isin, cap in mcap_data.items()
                ])
                cache_df.to_csv(AMFI_CACHE_FILE, index=False)
                logger.info(f"Saved {len(mcap_data)} market cap entries to cache")
            except Exception as e:
                logger.warning(f"Error saving market cap cache: {e}")
            return mcap_data
    except Exception as e:
        logger.warning(f"Error downloading Nifty indices for market cap: {e}")

    # Fallback: use stale cache if we have it
    if mcap_data:
        logger.info(f"Using stale market cap cache with {len(mcap_data)} entries")
        return mcap_data

    logger.warning("No market cap data available")
    return mcap_data


def classify_market_cap(isin: str, mcap_data: dict) -> str:
    """
    Classify a stock's market cap using AMFI data.

    Args:
        isin: The stock's ISIN code.
        mcap_data: Dict from load_market_cap_data().

    Returns:
        'Large Cap', 'Mid Cap', or 'Small Cap'.
        Stocks not in AMFI list default to 'Small Cap' (AMFI only lists top 250).
    """
    if not isin or not mcap_data:
        return 'Small Cap'
    return mcap_data.get(str(isin).strip(), 'Small Cap')


def add_classifications(df: pd.DataFrame, mcap_data: dict | None = None) -> pd.DataFrame:
    """
    Add classification columns to a DataFrame.
    Expects columns: SERIES, EXCHANGE, and optionally ISIN.

    Adds columns:
        - CATEGORY: 'Normal', 'T2T', 'SME', etc.
        - SETTLEMENT: 'T+1', 'T+2', 'T+1 (T2T)', etc.
        - RESTRICTIONS: Comma-separated restriction strings
        - IS_SME: True/False
        - MARKET_CAP: 'Large Cap', 'Mid Cap', 'Small Cap'

    Args:
        df: DataFrame with SERIES and EXCHANGE columns.
        mcap_data: Optional dict from load_market_cap_data().

    Returns:
        DataFrame with new classification columns added.
    """
    if df.empty:
        return df

    df = df.copy()

    # Category
    df['CATEGORY'] = df.apply(
        lambda row: classify_series(row.get('SERIES', ''), row.get('EXCHANGE', '')),
        axis=1
    )

    # Settlement
    df['SETTLEMENT'] = df['CATEGORY'].apply(get_settlement_info)

    # Restrictions
    df['RESTRICTIONS'] = df['CATEGORY'].apply(get_restrictions)

    # SME flag
    df['IS_SME'] = df.apply(
        lambda row: is_sme(row.get('SERIES', ''), row.get('EXCHANGE', '')),
        axis=1
    )

    # Market cap
    if mcap_data and 'ISIN' in df.columns:
        df['MARKET_CAP'] = df['ISIN'].apply(lambda x: classify_market_cap(x, mcap_data))
    else:
        df['MARKET_CAP'] = 'Small Cap'

    return df
