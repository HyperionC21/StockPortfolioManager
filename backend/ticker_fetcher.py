# GLOBAL IMPORTS
import pandas as pd
import yfinance as yf

# PROJECT IMPORTS
from .base import DataFetcher
from .fx_fetcher import FxFetcher
from .sql import queries
from utils import utils

from bs4 import BeautifulSoup
import requests

URL = 'https://www.bvb.ro/FinancialInstruments/Details/FinancialInstrumentsDetails.aspx?s={}'

def get_security_val(security):
    try:
        resp = requests.get(URL.format(security))
        soup = BeautifulSoup(resp.content, "html.parser")
        res = soup.find_all('tr')
        res = list(filter(lambda x: len(BeautifulSoup(str(x), 'html.parser').find_all('td', text='Ultimul pret')) > 0, res))[0]
        res = float(BeautifulSoup(str(res), 'html.parser').find('b').text.replace(',', '.'))
        res
        return res
    except:
        print(f'Failed to get value for security: {security}')

def get_security_pe_bvb(security):
    try:
        resp = requests.get(URL.format(security))
        soup = BeautifulSoup(resp.content, "html.parser")
        res = soup.find_all('tr')
        res = list(filter(lambda x: len(BeautifulSoup(str(x), 'html.parser').find_all('td', text='PER')) > 0, res))[0]
        res = float(BeautifulSoup(str(res), 'html.parser').find('b').text.replace(',', '.'))
        res
        return res
    except:
        print(f'Failed to get value for security: {security}')

class TickerFetcher(DataFetcher):
    def __init__(self, db_conn):
        super().__init__(db_conn)
    
    def fetch_all_transacted_tickers(self):
        return self.fetch_query(queries.ALL_TICKERS_QUERY)

    def fetch_ticker_prices(self, tickers, ref_date):
        tickers = list(map(lambda x: f"'{x}'", tickers))
        return self.fetch_query(queries.TICKER_PRICES_QUERY.format(ref_date, ",".join(tickers)))
    
    def fetch_ticker_fx(self, ref_date):
        tickers = self.fetch_all_transacted_tickers()
        fx_vals = FxFetcher(self.db_conn).fetch_fx_val(ref_date)

        tickers = list(map(lambda x: f"'{x}'", tickers['TICKER']))

        tickers_fx = self.fetch_query(queries.TICKERS_FX_QUERY.format(','.join(tickers)))
        tickers_fx = pd.merge(tickers_fx, fx_vals, on='CURRENCY_CD', how='inner')

        tickers_fx = tickers_fx[['TICKER', 'VALUE']]
        return tickers_fx
    
    def fetch_fst_trans_date_per_ticker(self):
        return self.fetch_query(queries.FST_TRANS_TICKER_QUERY)
    
    def fetch_ticker_hist(self, start_date, end_date):
        
        df_tickers = self.fetch_all_transacted_tickers()

        df_missing_tickers = self.fetch_query(queries.MISSING_TICKERS_DATA_QUERY.format(start_date, end_date))

        df_missing_tickers = df_missing_tickers[df_missing_tickers.TICKER.isin(df_tickers.TICKER)]
        
        for _, row in df_missing_tickers.iterrows():
            src = row['SRC']
            print(f'fetching {row["TICKER"]}')
            if src == 'YF':
                try:
                    ticker = yf.Ticker(row['TICKER'])
                    hist = ticker.history(start=row['FETCH_START_DT'], end=row['FETCH_END_DT']).reset_index()
                    hist['TICKER'] = row['TICKER']
                    hist = hist[hist.Date >= row['FETCH_START_DT']]
                    hist['Date'] = hist['Date'].apply(utils.date2str)
                except Exception as e:
                    print(e)
                    print(f'Ticker {row["TICKER"]} not found on yahoo finance')
            elif src == 'BVB':
                price = get_security_val(row['TICKER'])
                if price is None:
                    continue
                res = {
                    'Close' : [price],
                    'High' : [None],
                    'Low' : [None],
                    'Open' : [None],
                    'Date' : [utils.date2str(utils.datetime.now())],
                    'TICKER' : [row['TICKER']]
                }
                hist = pd.DataFrame(res)
            hist = hist[['TICKER', 'Date', 'Open', 'High', 'Low', 'Close']]
            hist.columns = list(map(lambda x: x.upper(), hist.columns))	
            try:
                self.db_conn.insert_data(hist, 'SECURITY_VALUES')
            except Exception as e:
                print(e)
                print('Failed to insert security history for {} on {}'.format(hist['TICKER'].iloc[0], hist['DATE'].iloc[0]))
                print(f'{row["FETCH_START_DT"]}')
    