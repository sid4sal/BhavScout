import os
import pandas as pd
from datetime import date
import logging
import requests
import zipfile
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_headers():
    return {'User-Agent': 'Mozilla/5.0'}

def extract_zip(resp_content, filename):
    with zipfile.ZipFile(io.BytesIO(resp_content)) as zf:
        csv_filename = zf.namelist()[0]
        with zf.open(csv_filename) as f:
            with open(filename, 'wb') as out_f:
                out_f.write(f.read())

def download_nse_bhavcopy(dt: date) -> str:
    fmt = '%Y%m%d'
    date_str = dt.strftime(fmt)
    filename = os.path.join(CACHE_DIR, f"nse_cm_{date_str}.csv")
    if os.path.exists(filename): return filename

    is_legacy = dt < date(2024, 7, 8)
    if is_legacy:
        mmm = dt.strftime('%b').upper()
        dd = dt.strftime('%d')
        fname = f"cm{dd}{mmm}{dt.year}bhav.csv.zip"
        url = f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{dt.year}/{mmm}/{fname}"
    else:
        url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"

    try:
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200 and resp.content[:2] == b'PK':
            extract_zip(resp.content, filename)
            return filename
    except Exception as e:
        logger.warning(f"Could not download NSE CM bhavcopy for {dt}: {e}")
    return None

def download_nse_fo_bhavcopy(dt: date) -> str:
    fmt = '%Y%m%d'
    date_str = dt.strftime(fmt)
    filename = os.path.join(CACHE_DIR, f"nse_fo_{date_str}.csv")
    if os.path.exists(filename): return filename

    is_legacy = dt < date(2024, 7, 8)
    if is_legacy:
        mmm = dt.strftime('%b').upper()
        dd = dt.strftime('%d')
        fname = f"fo{dd}{mmm}{dt.year}bhav.csv.zip"
        url = f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{dt.year}/{mmm}/{fname}"
    else:
        url = f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv.zip"

    try:
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200 and resp.content[:2] == b'PK':
            extract_zip(resp.content, filename)
            return filename
    except Exception as e:
        logger.warning(f"Could not download NSE FO bhavcopy for {dt}: {e}")
    return None

def download_nse_indices(dt: date) -> str:
    ddmmyyyy = dt.strftime('%d%m%Y')
    filename = os.path.join(CACHE_DIR, f"nse_idx_{ddmmyyyy}.csv")
    if os.path.exists(filename): return filename
    
    url = f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{ddmmyyyy}.csv"
    try:
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(resp.content)
            return filename
    except Exception as e:
        logger.warning(f"Could not download NSE Indices for {dt}: {e}")
    return None

def download_bse_indices(dt: date) -> str:
    ddmmyyyy = dt.strftime('%d%m%Y')
    filename = os.path.join(CACHE_DIR, f"bse_idx_{ddmmyyyy}.csv")
    if os.path.exists(filename): return filename
    
    url = f"https://www.bseindia.com/bsedata/Index_Bhavcopy/INDEXSummary_{ddmmyyyy}.csv"
    try:
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(resp.content)
            return filename
    except Exception as e:
        logger.warning(f"Could not download BSE Indices for {dt}: {e}")
    return None

def download_bse_bhavcopy(dt: date) -> str:
    date_str = dt.strftime('%Y%m%d')
    filename = os.path.join(CACHE_DIR, f"bse_eq_{date_str}.csv")
    if os.path.exists(filename): return filename
        
    url = f"https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{date_str}_F_0000.CSV"
    try:
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(resp.content)
            return filename
    except Exception as e:
        logger.warning(f"Could not download BSE bhavcopy for {dt}: {e}")
    return None

def download_bse_fo_bhavcopy(dt: date) -> str:
    date_str = dt.strftime('%Y%m%d')
    filename = os.path.join(CACHE_DIR, f"bse_fo_{date_str}.csv")
    if os.path.exists(filename): return filename
    
    url = f"https://www.bseindia.com/download/BhavCopy/Derivative/BhavCopy_BSE_FO_0_0_0_{date_str}_F_0000.CSV"
    try:
        resp = requests.get(url, headers=get_headers())
        if resp.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(resp.content)
            return filename
    except Exception as e:
        logger.warning(f"Could not download BSE FO bhavcopy for {dt}: {e}")
    return None

def classify_equity(symbol):
    sym = str(symbol).upper()
    if 'BEES' in sym or 'ETF' in sym:
        return 'ETF'
    return 'Equity'

def get_previous_trading_day(dt: date, markets: list[str]) -> date:
    from datetime import timedelta
    for i in range(1, 8):
        prev_dt = dt - timedelta(days=i)
        if prev_dt.weekday() < 5:
            # Check NSE or BSE CM bhavcopy as a market open indicator
            if "NSE" in markets and download_nse_bhavcopy(prev_dt):
                return prev_dt
            elif "BSE" in markets and download_bse_bhavcopy(prev_dt):
                return prev_dt
    return dt - timedelta(days=1)

def fetch_data_for_dates(dates: list[date], markets: list[str] = ["NSE"]) -> pd.DataFrame:
    all_data = []
    
    # 0. Prep extra date for PREVCLOSE calculation (Legacy FO handling)
    original_dates = set(dates)
    if dates:
        min_dt = min(dates)
        # If legacy NSE F&O could be involved, we need the prev day
        if min_dt < date(2024, 7, 8) and "NSE" in markets:
            prev_dt = get_previous_trading_day(min_dt, markets)
            if prev_dt not in dates:
                dates = [prev_dt] + dates

    for dt in dates:
        if "NSE" in markets:
            # 1. NSE Equity
            eq_file = download_nse_bhavcopy(dt)
            if eq_file and os.path.exists(eq_file):
                try:
                    df_eq = pd.read_csv(eq_file)
                    df_eq.columns = df_eq.columns.str.strip()
                    if 'TckrSymb' in df_eq.columns:
                        df_eq['SERIES'] = df_eq['SctySrs'].str.strip()
                        df_eq['SYMBOL'] = df_eq['TckrSymb'].str.strip()
                        df_eq = df_eq[df_eq['SERIES'].isin(['EQ', 'BE'])]
                        df_eq['INSTRUMENT_TYPE'] = df_eq['SYMBOL'].apply(classify_equity)
                        df_eq['DATE'] = pd.to_datetime(df_eq['TradDt'])
                        df_eq = df_eq.rename(columns={'OpnPric': 'OPEN', 'HghPric': 'HIGH', 'LwPric': 'LOW', 'ClsPric': 'CLOSE', 'PrvsClsgPric': 'PREVCLOSE', 'TtlTradgVol': 'VOLUME', 'TtlTrfVal': 'TURNOVER'})
                    else:
                        df_eq['SERIES'] = df_eq['SERIES'].str.strip()
                        df_eq['SYMBOL'] = df_eq['SYMBOL'].str.strip()
                        df_eq = df_eq[df_eq['SERIES'].isin(['EQ', 'BE'])]
                        df_eq['INSTRUMENT_TYPE'] = df_eq['SYMBOL'].apply(classify_equity)
                        df_eq['DATE'] = pd.to_datetime(df_eq['TIMESTAMP'] if 'TIMESTAMP' in df_eq.columns else (df_eq['DATE1'] if 'DATE1' in df_eq.columns else dt))
                        df_eq = df_eq.rename(columns={'OPEN_PRICE': 'OPEN', 'HIGH_PRICE': 'HIGH', 'LOW_PRICE': 'LOW', 'CLOSE_PRICE': 'CLOSE', 'PREV_CLOSE': 'PREVCLOSE', 'TOTTRDQTY': 'VOLUME', 'TTL_TRD_QNTY': 'VOLUME', 'TOTTRDVAL': 'TURNOVER', 'TURNOVER_LACS': 'TURNOVER'})
                        if 'TURNOVER' in df_eq.columns and df_eq['TURNOVER'].mean() < 1e7:
                            df_eq['TURNOVER'] = df_eq['TURNOVER'] * 100000
                    df_eq['SYMBOL'] = df_eq['SYMBOL'] + ' (NSE)'
                    df_eq = df_eq[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                    all_data.append(df_eq)
                except Exception as e:
                    logger.error(f"Error parsing NSE eq file {eq_file}: {e}")

            # 2. NSE FO
            fo_file = download_nse_fo_bhavcopy(dt)
            if fo_file and os.path.exists(fo_file):
                try:
                    df_fo = pd.read_csv(fo_file)
                    df_fo.columns = df_fo.columns.str.strip()
                    if 'FinInstrmTp' in df_fo.columns:
                        df_fo['INSTRUMENT_TYPE'] = df_fo['FinInstrmTp'].apply(lambda x: 'Futures' if x in ['STF','IDF'] else ('Options' if x in ['STO','IDO'] else 'Other'))
                        df_fo['SYMBOL'] = df_fo['TckrSymb'].astype(str) + '_' + df_fo['FinInstrmTp'].astype(str) + '_' + df_fo['XpryDt'].astype(str)
                        df_fo['DATE'] = pd.to_datetime(df_fo['TradDt'])
                        df_fo = df_fo.rename(columns={'OpnPric': 'OPEN', 'HghPric': 'HIGH', 'LwPric': 'LOW', 'ClsPric': 'CLOSE', 'PrvsClsgPric': 'PREVCLOSE', 'TtlTradgVol': 'VOLUME', 'TtlTrfVal': 'TURNOVER'})
                    else:
                        df_fo['DATE'] = pd.to_datetime(df_fo['TIMESTAMP'] if 'TIMESTAMP' in df_fo.columns else dt)
                        df_fo['INSTRUMENT_TYPE'] = df_fo['INSTRUMENT'].apply(lambda x: 'Futures' if str(x).startswith('FUT') else ('Options' if str(x).startswith('OPT') else 'Other'))
                        df_fo['SYMBOL'] = df_fo['SYMBOL'].astype(str) + '_' + df_fo['INSTRUMENT'].astype(str) + '_' + df_fo['EXPIRY_DT'].astype(str)
                        df_fo['PREVCLOSE'] = float('nan') 
                        df_fo = df_fo.rename(columns={'CONTRACTS': 'VOLUME', 'VAL_INLAKH': 'TURNOVER'})
                        if 'TURNOVER' in df_fo.columns:
                            df_fo['TURNOVER'] = df_fo['TURNOVER'] * 100000
                    df_fo['SYMBOL'] = df_fo['SYMBOL'] + ' (NSE)'
                    df_fo = df_fo[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                    all_data.append(df_fo)
                except Exception as e:
                    logger.error(f"Error parsing NSE fo file {fo_file}: {e}")
                    
            # 3. NSE Indices
            idx_file = download_nse_indices(dt)
            if idx_file and os.path.exists(idx_file):
                try:
                    df_idx = pd.read_csv(idx_file)
                    df_idx.columns = df_idx.columns.str.strip()
                    df_idx['INSTRUMENT_TYPE'] = 'Index'
                    df_idx = df_idx.rename(columns={
                        'Index Name': 'SYMBOL', 'Index Date': 'DATE',
                        'Open Index Value': 'OPEN', 'High Index Value': 'HIGH', 
                        'Low Index Value': 'LOW', 'Closing Index Value': 'CLOSE',
                        'Volume': 'VOLUME', 'Turnover (Rs. Cr.)': 'TURNOVER'
                    })
                    if 'TURNOVER' in df_idx.columns:
                        # Turnover is in Rs. Cr., convert to absolute (1 Cr = 10,000,000)
                        df_idx['TURNOVER'] = pd.to_numeric(df_idx['TURNOVER'], errors='coerce') * 10000000
                    if 'VOLUME' in df_idx.columns:
                        df_idx['VOLUME'] = pd.to_numeric(df_idx['VOLUME'], errors='coerce').fillna(0)
                    
                    df_idx['DATE'] = pd.to_datetime(df_idx['DATE'], format='%d-%m-%Y', errors='coerce')
                    # Calculate PREVCLOSE using Points Change
                    if 'Points Change' in df_idx.columns:
                        df_idx['PREVCLOSE'] = pd.to_numeric(df_idx['CLOSE'], errors='coerce') - pd.to_numeric(df_idx['Points Change'], errors='coerce')
                    else:
                        df_idx['PREVCLOSE'] = float('nan')
                    
                    df_idx['SYMBOL'] = df_idx['SYMBOL'] + ' (NSE)'
                    df_idx = df_idx[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                    all_data.append(df_idx)
                except Exception as e:
                    logger.error(f"Error parsing NSE index file {idx_file}: {e}")

        if "BSE" in markets:
            # 4. BSE Equity
            bse_file = download_bse_bhavcopy(dt)
            if bse_file and os.path.exists(bse_file):
                try:
                    df_bse = pd.read_csv(bse_file)
                    df_bse.columns = df_bse.columns.str.strip()
                    if 'TckrSymb' in df_bse.columns:
                        df_bse['SERIES'] = df_bse['SctySrs'].str.strip()
                        df_bse['SYMBOL'] = df_bse['TckrSymb'].str.strip()
                        df_bse['INSTRUMENT_TYPE'] = df_bse['SYMBOL'].apply(classify_equity)
                        df_bse['DATE'] = pd.to_datetime(df_bse['TradDt'])
                        df_bse = df_bse.rename(columns={'OpnPric': 'OPEN', 'HghPric': 'HIGH', 'LwPric': 'LOW', 'ClsPric': 'CLOSE', 'PrvsClsgPric': 'PREVCLOSE', 'TtlTradgVol': 'VOLUME', 'TtlTrfVal': 'TURNOVER'})
                        df_bse['SYMBOL'] = df_bse['SYMBOL'] + ' (BSE)'
                        df_bse = df_bse[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                        all_data.append(df_bse)
                except Exception as e:
                    logger.error(f"Error parsing BSE eq file {bse_file}: {e}")
                    
            # 5. BSE FO
            bse_fo_file = download_bse_fo_bhavcopy(dt)
            if bse_fo_file and os.path.exists(bse_fo_file):
                try:
                    df_bse_fo = pd.read_csv(bse_fo_file)
                    df_bse_fo.columns = df_bse_fo.columns.str.strip()
                    if 'FinInstrmTp' in df_bse_fo.columns:
                        df_bse_fo['INSTRUMENT_TYPE'] = df_bse_fo['FinInstrmTp'].apply(lambda x: 'Futures' if x in ['STF','IDF'] else ('Options' if x in ['STO','IDO'] else 'Other'))
                        df_bse_fo['SYMBOL'] = df_bse_fo['TckrSymb'].astype(str) + '_' + df_bse_fo['FinInstrmTp'].astype(str) + '_' + df_bse_fo['XpryDt'].astype(str)
                        df_bse_fo['DATE'] = pd.to_datetime(df_bse_fo['TradDt'])
                        df_bse_fo = df_bse_fo.rename(columns={'OpnPric': 'OPEN', 'HghPric': 'HIGH', 'LwPric': 'LOW', 'ClsPric': 'CLOSE', 'PrvsClsgPric': 'PREVCLOSE', 'TtlTradgVol': 'VOLUME', 'TtlTrfVal': 'TURNOVER'})
                        df_bse_fo['SYMBOL'] = df_bse_fo['SYMBOL'] + ' (BSE)'
                        df_bse_fo = df_bse_fo[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                        all_data.append(df_bse_fo)
                except Exception as e:
                    logger.error(f"Error parsing BSE fo file {bse_fo_file}: {e}")

            # 6. BSE Indices
            bse_idx_file = download_bse_indices(dt)
            if bse_idx_file and os.path.exists(bse_idx_file):
                try:
                    df_bse_idx = pd.read_csv(bse_idx_file)
                    df_bse_idx.columns = df_bse_idx.columns.str.strip()
                    df_bse_idx['INSTRUMENT_TYPE'] = 'Index'
                    df_bse_idx['DATE'] = pd.to_datetime(dt)
                    df_bse_idx = df_bse_idx.rename(columns={
                        'IndexName': 'SYMBOL', 'OpenPrice': 'OPEN', 'HighPrice': 'HIGH',
                        'LowPrice': 'LOW', 'ClosePrice': 'CLOSE', 'PreviousClose': 'PREVCLOSE'
                    })
                    df_bse_idx['VOLUME'] = 0.0
                    df_bse_idx['TURNOVER'] = 0.0
                    df_bse_idx['SYMBOL'] = df_bse_idx['SYMBOL'] + ' (BSE)'
                    df_bse_idx = df_bse_idx[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                    all_data.append(df_bse_idx)
                except Exception as e:
                    logger.error(f"Error parsing BSE index file {bse_idx_file}: {e}")

    if not all_data:
        return pd.DataFrame()
        
    final_df = pd.concat(all_data, ignore_index=True)
    final_df = final_df.drop_duplicates(subset=['SYMBOL', 'INSTRUMENT_TYPE', 'DATE'])
    
    # Calculate PREVCLOSE using shift(1) for any NaNs
    final_df = final_df.sort_values(by=['SYMBOL', 'DATE'])
    final_df['PREVCLOSE'] = final_df['PREVCLOSE'].fillna(final_df.groupby('SYMBOL')['CLOSE'].shift(1))
    
    # Drop any extra dates that were fetched solely for PREVCLOSE calculation
    requested_dates_dt = pd.to_datetime(list(original_dates))
    final_df = final_df[final_df['DATE'].isin(requested_dates_dt)].copy()
    
    return final_df
