import os
import pandas as pd
from datetime import date
import logging
from jugaad_data.nse import bhavcopy_save, bhavcopy_fo_save

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_bhavcopy_filename(dt: date, is_fo: bool = False) -> str:
    # jugaad-data saves files in a specific format
    # e.g., cm01Jan2021bhav.csv for equity
    # fo01Jan2021bhav.csv for f&o
    month_str = dt.strftime("%b").capitalize()
    date_str = dt.strftime("%d")
    year_str = dt.strftime("%Y")
    if is_fo:
        return os.path.join(CACHE_DIR, f"fo{date_str}{month_str}{year_str}bhav.csv")
    else:
        return os.path.join(CACHE_DIR, f"cm{date_str}{month_str}{year_str}bhav.csv")

def download_bhavcopy(dt: date, is_fo: bool = False) -> str:
    filename = get_bhavcopy_filename(dt, is_fo)
    if os.path.exists(filename):
        return filename
    
    try:
        if is_fo:
            bhavcopy_fo_save(dt, CACHE_DIR)
        else:
            bhavcopy_save(dt, CACHE_DIR)
        return filename
    except Exception as e:
        logger.warning(f"Could not download bhavcopy for {dt} (FO={is_fo}): {e}")
        return None

def fetch_data_for_dates(dates: list[date]) -> pd.DataFrame:
    all_data = []
    
    for dt in dates:
        # Download Equity
        eq_file = download_bhavcopy(dt, is_fo=False)
        if eq_file and os.path.exists(eq_file):
            try:
                df_eq = pd.read_csv(eq_file)
                # Filter out unwanted spaces in columns
                df_eq.columns = df_eq.columns.str.strip()
                
                # Check for new format vs old format
                if 'TckrSymb' in df_eq.columns:
                    # New Format
                    df_eq['SERIES'] = df_eq['SctySrs'].str.strip()
                    df_eq['SYMBOL'] = df_eq['TckrSymb'].str.strip()
                    df_eq = df_eq[df_eq['SERIES'].isin(['EQ', 'BE'])]
                    df_eq['INSTRUMENT_TYPE'] = 'Equity'
                    df_eq['DATE'] = pd.to_datetime(df_eq['TradDt'])
                    df_eq = df_eq.rename(columns={
                        'OpnPric': 'OPEN',
                        'HghPric': 'HIGH',
                        'LwPric': 'LOW',
                        'ClsPric': 'CLOSE',
                        'PrvsClsgPric': 'PREVCLOSE',
                        'TtlTradgVol': 'VOLUME',
                        'TtlTrfVal': 'TURNOVER'
                    })
                    # Turnover is already in actual rupees
                else:
                    # Old Format
                    df_eq['SERIES'] = df_eq['SERIES'].str.strip()
                    df_eq['SYMBOL'] = df_eq['SYMBOL'].str.strip()
                    df_eq = df_eq[df_eq['SERIES'].isin(['EQ', 'BE'])]
                    df_eq['INSTRUMENT_TYPE'] = 'Equity'
                    df_eq['DATE'] = pd.to_datetime(df_eq['DATE1'])
                    df_eq = df_eq.rename(columns={
                        'OPEN_PRICE': 'OPEN',
                        'HIGH_PRICE': 'HIGH',
                        'LOW_PRICE': 'LOW',
                        'CLOSE_PRICE': 'CLOSE',
                        'PREV_CLOSE': 'PREVCLOSE',
                        'TTL_TRD_QNTY': 'VOLUME',
                        'TURNOVER_LACS': 'TURNOVER'
                    })
                    # Convert turnover in Lakhs to raw value to match
                    df_eq['TURNOVER'] = df_eq['TURNOVER'] * 100000
                
                df_eq = df_eq[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                all_data.append(df_eq)
            except Exception as e:
                logger.error(f"Error reading eq file {eq_file}: {e}")

        # Download FO
        fo_file = download_bhavcopy(dt, is_fo=True)
        if fo_file and os.path.exists(fo_file):
            try:
                df_fo = pd.read_csv(fo_file)
                df_fo.columns = df_fo.columns.str.strip()
                if 'TIMESTAMP' in df_fo.columns:
                    df_fo['DATE'] = pd.to_datetime(df_fo['TIMESTAMP'])
                elif 'TradDt' in df_fo.columns:
                    df_fo['DATE'] = pd.to_datetime(df_fo['TradDt'])
                else:
                    df_fo['DATE'] = pd.to_datetime(dt)
                # F&O has different columns: INSTRUMENT, SYMBOL, EXPIRY_DT, STRIKE_PR, OPTION_TYP, OPEN, HIGH, LOW, CLOSE, SETTLE_PR, CONTRACTS, VAL_INLAKH, OPEN_INT
                
                # Classify into Futures and Options
                def get_inst_type(inst):
                    if str(inst).startswith('FUT'): return 'Futures'
                    if str(inst).startswith('OPT'): return 'Options'
                    return 'Other'
                
                df_fo['INSTRUMENT_TYPE'] = df_fo['INSTRUMENT'].apply(get_inst_type)
                
                # We need a unique identifier for F&O, e.g., SYMBOL + EXPIRY + STRIKE + OPTION_TYP
                df_fo['SYMBOL'] = df_fo['SYMBOL'] + '_' + df_fo['INSTRUMENT'] + '_' + df_fo['EXPIRY_DT']
                # Create a proxy for PREVCLOSE. F&O bhavcopy doesn't explicitly have PREVCLOSE in the same way, but it has OPEN and CLOSE.
                # If we need PREVCLOSE, we'll calculate it later by grouping or just use SETTLE_PR if available. 
                # For simplicity, if we don't have previous day, we just set it to NaN and handle it in screener
                if 'PREVCLOSE' not in df_fo.columns:
                    df_fo['PREVCLOSE'] = float('nan') # Will be calculated across days if needed
                
                df_fo = df_fo.rename(columns={
                    'CONTRACTS': 'VOLUME',
                    'VAL_INLAKH': 'TURNOVER'
                })
                # Turnover is in Lakhs for FO, convert to raw value to match equity
                if 'TURNOVER' in df_fo.columns:
                    df_fo['TURNOVER'] = df_fo['TURNOVER'] * 100000

                df_fo = df_fo[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                all_data.append(df_fo)
            except Exception as e:
                logger.error(f"Error reading fo file {fo_file}: {e}")

    if not all_data:
        return pd.DataFrame()
        
    final_df = pd.concat(all_data, ignore_index=True)
    # Deduplicate in case a holiday fetched the previous day's data
    final_df = final_df.drop_duplicates(subset=['SYMBOL', 'INSTRUMENT_TYPE', 'DATE'])
    return final_df
