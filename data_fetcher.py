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

def download_nse_bhavcopy(dt: date) -> str:
    fmt = '%Y%m%d'
    date_str = dt.strftime(fmt)
    filename = os.path.join(CACHE_DIR, f"nse_cm_{date_str}.csv")
    
    if os.path.exists(filename):
        return filename

    is_legacy = dt < date(2024, 7, 8)
    if is_legacy:
        mmm = dt.strftime('%b').upper()
        dd = dt.strftime('%d')
        fname = f"cm{dd}{mmm}{dt.year}bhav.csv.zip"
        url = f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{dt.year}/{mmm}/{fname}"
    else:
        url = f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{date_str}_F_0000.csv.zip"

    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200 and resp.content[:2] == b'PK':
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                csv_filename = zf.namelist()[0]
                with zf.open(csv_filename) as f:
                    with open(filename, 'wb') as out_f:
                        out_f.write(f.read())
            return filename
        else:
            logger.warning(f"Could not download NSE CM bhavcopy for {dt}: HTTP {resp.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Could not download NSE CM bhavcopy for {dt}: {e}")
        return None

def download_nse_fo_bhavcopy(dt: date) -> str:
    fmt = '%Y%m%d'
    date_str = dt.strftime(fmt)
    filename = os.path.join(CACHE_DIR, f"nse_fo_{date_str}.csv")
    
    if os.path.exists(filename):
        return filename

    is_legacy = dt < date(2024, 7, 8)
    if is_legacy:
        mmm = dt.strftime('%b').upper()
        dd = dt.strftime('%d')
        fname = f"fo{dd}{mmm}{dt.year}bhav.csv.zip"
        url = f"https://nsearchives.nseindia.com/content/historical/DERIVATIVES/{dt.year}/{mmm}/{fname}"
    else:
        url = f"https://nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_{date_str}_F_0000.csv.zip"

    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200 and resp.content[:2] == b'PK':
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                csv_filename = zf.namelist()[0]
                with zf.open(csv_filename) as f:
                    with open(filename, 'wb') as out_f:
                        out_f.write(f.read())
            return filename
        else:
            logger.warning(f"Could not download NSE FO bhavcopy for {dt}: HTTP {resp.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Could not download NSE FO bhavcopy for {dt}: {e}")
        return None

def download_bse_bhavcopy(dt: date) -> str:
    fmt = '%Y%m%d'
    date_str = dt.strftime(fmt)
    filename = os.path.join(CACHE_DIR, f"bse_eq_{date_str}.csv")
    
    if os.path.exists(filename):
        return filename
        
    url = f"https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{date_str}_F_0000.CSV"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200 and resp.headers.get('Content-Type', '') == 'application/octet-stream':
            with open(filename, 'wb') as f:
                f.write(resp.content)
            return filename
        else:
            logger.warning(f"Could not download BSE bhavcopy for {dt}: HTTP {resp.status_code}")
            return None
    except Exception as e:
        logger.warning(f"Could not download BSE bhavcopy for {dt}: {e}")
        return None

def fetch_data_for_dates(dates: list[date], market: str = "NSE") -> pd.DataFrame:
    all_data = []
    
    for dt in dates:
        if market in ["NSE", "Both"]:
            # Download NSE Equity
            eq_file = download_nse_bhavcopy(dt)
            if eq_file and os.path.exists(eq_file):
                try:
                    df_eq = pd.read_csv(eq_file)
                    df_eq.columns = df_eq.columns.str.strip()
                    
                    if 'TckrSymb' in df_eq.columns:
                        # New ISO 20022 Format
                        df_eq['SERIES'] = df_eq['SctySrs'].str.strip()
                        df_eq['SYMBOL'] = df_eq['TckrSymb'].str.strip()
                        df_eq = df_eq[df_eq['SERIES'].isin(['EQ', 'BE'])]
                        df_eq['INSTRUMENT_TYPE'] = 'Equity'
                        df_eq['DATE'] = pd.to_datetime(df_eq['TradDt'])
                        df_eq = df_eq.rename(columns={
                            'OpnPric': 'OPEN', 'HghPric': 'HIGH', 'LwPric': 'LOW', 'ClsPric': 'CLOSE',
                            'PrvsClsgPric': 'PREVCLOSE', 'TtlTradgVol': 'VOLUME', 'TtlTrfVal': 'TURNOVER'
                        })
                    else:
                        # Legacy Format
                        df_eq['SERIES'] = df_eq['SERIES'].str.strip()
                        df_eq['SYMBOL'] = df_eq['SYMBOL'].str.strip()
                        df_eq = df_eq[df_eq['SERIES'].isin(['EQ', 'BE'])]
                        df_eq['INSTRUMENT_TYPE'] = 'Equity'
                        df_eq['DATE'] = pd.to_datetime(df_eq['TIMESTAMP'] if 'TIMESTAMP' in df_eq.columns else (df_eq['DATE1'] if 'DATE1' in df_eq.columns else dt))
                        df_eq = df_eq.rename(columns={
                            'OPEN_PRICE': 'OPEN', 'HIGH_PRICE': 'HIGH', 'LOW_PRICE': 'LOW', 'CLOSE_PRICE': 'CLOSE',
                            'PREV_CLOSE': 'PREVCLOSE', 'TOTTRDQTY': 'VOLUME', 'TTL_TRD_QNTY': 'VOLUME', 'TOTTRDVAL': 'TURNOVER', 'TURNOVER_LACS': 'TURNOVER'
                        })
                        if 'TURNOVER' in df_eq.columns and df_eq['TURNOVER'].mean() < 1e7:
                            df_eq['TURNOVER'] = df_eq['TURNOVER'] * 100000
                    
                    df_eq['SYMBOL'] = df_eq['SYMBOL'] + ' (NSE)'
                    df_eq = df_eq[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                    all_data.append(df_eq)
                except Exception as e:
                    logger.error(f"Error reading NSE eq file {eq_file}: {e}")

            # Download NSE FO
            fo_file = download_nse_fo_bhavcopy(dt)
            if fo_file and os.path.exists(fo_file):
                try:
                    df_fo = pd.read_csv(fo_file)
                    df_fo.columns = df_fo.columns.str.strip()
                    
                    if 'FinInstrmTp' in df_fo.columns:
                        # New ISO 20022 Format
                        def get_inst_type_iso(inst):
                            if inst in ['STF', 'IDF']: return 'Futures'
                            if inst in ['STO', 'IDO']: return 'Options'
                            return 'Other'
                        df_fo['INSTRUMENT_TYPE'] = df_fo['FinInstrmTp'].apply(get_inst_type_iso)
                        df_fo['SYMBOL'] = df_fo['TckrSymb'].astype(str) + '_' + df_fo['FinInstrmTp'].astype(str) + '_' + df_fo['XpryDt'].astype(str)
                        df_fo['DATE'] = pd.to_datetime(df_fo['TradDt'])
                        df_fo = df_fo.rename(columns={
                            'OpnPric': 'OPEN', 'HghPric': 'HIGH', 'LwPric': 'LOW', 'ClsPric': 'CLOSE',
                            'PrvsClsgPric': 'PREVCLOSE', 'TtlTradgVol': 'VOLUME', 'TtlTrfVal': 'TURNOVER'
                        })
                    else:
                        # Legacy FO format
                        if 'TIMESTAMP' in df_fo.columns:
                            df_fo['DATE'] = pd.to_datetime(df_fo['TIMESTAMP'])
                        else:
                            df_fo['DATE'] = pd.to_datetime(dt)
                            
                        def get_inst_type_legacy(inst):
                            if str(inst).startswith('FUT'): return 'Futures'
                            if str(inst).startswith('OPT'): return 'Options'
                            return 'Other'
                        
                        df_fo['INSTRUMENT_TYPE'] = df_fo['INSTRUMENT'].apply(get_inst_type_legacy)
                        df_fo['SYMBOL'] = df_fo['SYMBOL'] + '_' + df_fo['INSTRUMENT'] + '_' + df_fo['EXPIRY_DT']
                        
                        if 'PREVCLOSE' not in df_fo.columns:
                            df_fo['PREVCLOSE'] = float('nan') 
                        
                        df_fo = df_fo.rename(columns={
                            'CONTRACTS': 'VOLUME',
                            'VAL_INLAKH': 'TURNOVER'
                        })
                        if 'TURNOVER' in df_fo.columns:
                            df_fo['TURNOVER'] = df_fo['TURNOVER'] * 100000

                    df_fo['SYMBOL'] = df_fo['SYMBOL'] + ' (NSE)'
                    df_fo = df_fo[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                    all_data.append(df_fo)
                except Exception as e:
                    logger.error(f"Error reading NSE fo file {fo_file}: {e}")

        if market in ["BSE", "Both"]:
            bse_file = download_bse_bhavcopy(dt)
            if bse_file and os.path.exists(bse_file):
                try:
                    df_bse = pd.read_csv(bse_file)
                    df_bse.columns = df_bse.columns.str.strip()
                    
                    if 'TckrSymb' in df_bse.columns:
                        df_bse['SERIES'] = df_bse['SctySrs'].str.strip()
                        df_bse['SYMBOL'] = df_bse['TckrSymb'].str.strip() + ' (BSE)'
                        df_bse['INSTRUMENT_TYPE'] = 'Equity'
                        df_bse['DATE'] = pd.to_datetime(df_bse['TradDt'])
                        df_bse = df_bse.rename(columns={
                            'OpnPric': 'OPEN', 'HghPric': 'HIGH', 'LwPric': 'LOW', 'ClsPric': 'CLOSE',
                            'PrvsClsgPric': 'PREVCLOSE', 'TtlTradgVol': 'VOLUME', 'TtlTrfVal': 'TURNOVER'
                        })
                        df_bse = df_bse[['SYMBOL', 'INSTRUMENT_TYPE', 'DATE', 'OPEN', 'HIGH', 'LOW', 'CLOSE', 'PREVCLOSE', 'VOLUME', 'TURNOVER']]
                        all_data.append(df_bse)
                except Exception as e:
                    logger.error(f"Error reading BSE file {bse_file}: {e}")

    if not all_data:
        return pd.DataFrame()
        
    final_df = pd.concat(all_data, ignore_index=True)
    final_df = final_df.drop_duplicates(subset=['SYMBOL', 'INSTRUMENT_TYPE', 'DATE'])
    return final_df
