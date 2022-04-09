from importlib_metadata import re
import pandas as pd
from .base import DataFetcher

class Reporter:
    def __init__(self, data_fecther):
        self._data_fetcher = data_fecther

    def get_comp(self, portfolio_id, ref_date):
        portfolio_composition = self._data_fetcher.fetch_portfolio_composition(portfolio_id, ref_date)

        tickers = list(map(lambda x: f"'{x}'", list(portfolio_composition['TICKER'])))

        ticker_prices = self._data_fetcher.fetch_ticker_prices(tickers, ref_date)

        df_out = pd.merge(portfolio_composition, ticker_prices, on='TICKER', how='left')

        ticker_fx = self._data_fetcher.fetch_ticker_fx(ref_date).rename(columns={'VALUE' : 'FX'})

        df_out = pd.merge(df_out, ticker_fx, on='TICKER', how='left')
        df_out['FX'] = df_out['FX'].fillna(1)

        df_out['VALUE'] = df_out['N_SHARES'] * df_out['PRICE'] * df_out['FX']

        return df_out

    def get_value_based_portf_distrib(self, portfolio_id, ref_date, hue=None):
        df_out = self.get_comp(portfolio_id, ref_date)

        if hue is None:
            res = df_out.groupby('TICKER')['VALUE'].sum() / df_out['VALUE'].sum()
            print(res)
            res = res.to_dict()
        elif hue == ''
        
        return res

    def get_nav_cost(self, portfolio_id, ref_date):
        df_out = self.get_comp(portfolio_id, ref_date)

        nav = df_out['VALUE'].sum()
        cost = df_out['TOTAL_COST'].sum()

        return {
            'nav' : nav,
            'cost' : cost
        }

