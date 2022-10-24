# GLOBAL IMPORTS
import yfinance as yf

# PROJECT IMPORTS
from .base import DataFetcher
from .sql import queries
from utils import utils

class FxFetcher(DataFetcher):
    def __init__(self, db_conn):
        super().__init__(db_conn)
    
    def fetch_currencies(self):
        return self.fetch_query(queries.CURRENCY_QUERY)

    def fetch_fx(self, start_date, end_date):

        currencies = self.fetch_currencies()

        for _, row in currencies.iterrows():
            ticker = yf.Ticker(row['CURRENCY_CD'])
            curr_hist = ticker.history(start=start_date, end=end_date).reset_index()
            curr_hist.columns = list(map(lambda x: x.upper(), curr_hist.columns))	

            curr_hist = curr_hist[['CLOSE', 'DATE']]
            curr_hist.rename(columns={
                'CLOSE' : 'VALUE'
            }, inplace=True)
            curr_hist['CURRENCY_CD'] = row['CURRENCY_CD']

            self.db_conn.insert_data(curr_hist, 'FX')

    def fetch_fx_val(self, ref_date):
        return self.fetch_query(queries.FX_VAL_QUERY.format(ref_date))

    def fetch_missing_fx(self, start_dt, end_dt):
        df_missing = self.fetch_query(queries.FX_MISSING_INTERVALS.format(start_dt, end_dt))

        for _, row in df_missing.iterrows():
            ticker = yf.Ticker(row['CURRENCY_CD'])

            try:
                curr_hist = ticker.history(start=row['FETCH_START_DT'], end=row['FETCH_END_DT']).reset_index()
            except:
                print('Error on: ')
                print(row)
                print('============')
            curr_hist.columns = list(map(lambda x: x.upper(), curr_hist.columns))	

            curr_hist = curr_hist[['CLOSE', 'DATE']]
            curr_hist.rename(columns={
                'CLOSE' : 'VALUE'
            }, inplace=True)
            curr_hist['CURRENCY_CD'] = row['CURRENCY_CD']
            curr_hist['DATE'] = curr_hist['DATE'].apply(utils.date2str)
            try:
                self.db_conn.insert_data(curr_hist, 'FX')
            except:
                print('Failed to insert: ', curr_hist, ' in FX')