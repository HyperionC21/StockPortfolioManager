import pandas as pd
from .base import DataFetcher

class Reporter:
    def __init__(self, data_fecther):
        self._data_fetcher = data_fecther

    def get_portfolio_info(self, portfolio_id, ref_date):
        portfolio_composition = self._data_fetcher.fetch_portfolio_composition(portfolio_id, ref_date)

        tickers = list(map(lambda x: f"'{x}'", list(portfolio_composition['TICKER'])))

        ticker_prices = self._data_fetcher.fetch_ticker_prices(tickers, ref_date)

        df_out = pd.merge(portfolio_composition, ticker_prices, on='TICKER', how='inner')

        ticker_fx = self._data_fetcher.fetch_ticker_fx(ref_date).rename(columns={'VALUE' : 'FX'})

        df_out = pd.merge(df_out, ticker_fx, on='TICKER', how='inner')
        df_out['FX'] = df_out['FX'].fillna(1)


        df_out['VALUE'] = df_out['N_SHARES'] * df_out['PRICE'] * df_out['FX']
        
        nav_at_dt = df_out['VALUE'].sum()
        cost_at_dt = df_out['TOTAL_COST'].sum()

        profit = nav_at_dt - cost_at_dt
        profit_perc =  profit * 100 / cost_at_dt

        res = {
            'nav' : nav_at_dt,
            'cost' : cost_at_dt,
            'profit_perc' : profit_perc,
            'profit' : profit,
            'df' : df_out
        }

        return res
