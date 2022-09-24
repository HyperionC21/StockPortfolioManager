# GLOBAL IMPORTS
import pandas as pd
import yfinance as yf

# PROJECT IMPORTS
from .base import DataFetcher
from .fx_fetcher import FxFetcher
from .sql import queries
from utils import utils

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

        hists = []
        for _, row in df_tickers.iterrows():
            try:
                ticker = yf.Ticker(row['TICKER'])
                hist = ticker.history(start=start_date, end=end_date).reset_index()
                hist['TICKER'] = row['TICKER']
                hists.append(hist)
            except Exception as e:
                print(e)
                print(f'Ticker {row["TICKER"]} not found on yahoo finance')

        hist = pd.concat(hists, axis=0)
        hist = hist[['TICKER', 'Date', 'Open', 'High', 'Low', 'Close']]
        hist.columns = list(map(lambda x: x.upper(), hist.columns))	

        try:
            self.db_conn.insert_data(hist, 'SECURITY_VALUES')
        except Exception as e:
            print(e)

        return hist
    