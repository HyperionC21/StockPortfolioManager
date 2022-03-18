import pandas as pd
from .base import DataFetcher

class Reporter:
    def __init__(self, data_fecther):
        self._data_fetcher = data_fecther



    def get_portfolio_nav(self, portfolio_id, ref_date):
        portfolio_composition = self._data_fetcher.fetch_portfolio_composition(portfolio_id, ref_date)

        tickers = list(map(lambda x: f"'{x}'", list(portfolio_composition['TICKER'])))

        ticker_prices = self._data_fetcher.fetch_ticker_prices(tickers, ref_date)

        df_out = pd.merge(portfolio_composition, ticker_prices, on='TICKER', how='inner')

        return df_out
