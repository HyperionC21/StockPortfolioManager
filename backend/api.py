from datetime import datetime
import imp
import pandas as pd
import numpy as np
from . import fx_fetcher, misc_fetcher, ticker_fetcher, base
from utils import utils



class PortfolioStats:
    def __init__(self, db_path, ref_date, ref_profit=None) -> None:
        self.db_conn = base.BaseDBConnector(db_path)
        self.fx_fetcher = fx_fetcher.FxFetcher(self.db_conn)
        self.misc_fetcher = misc_fetcher.MiscFetcher(self.db_conn)
        self.ticker_fetcher = ticker_fetcher.TickerFetcher(self.db_conn)

        self.ref_profit = ref_profit

        df_portfolio = self.misc_fetcher.fetch_portfolio_composition(1, ref_date=ref_date)
        prices = self.ticker_fetcher.fetch_ticker_prices(tickers = df_portfolio.TICKER, ref_date=ref_date)
        ticker_fx = self.ticker_fetcher.fetch_ticker_fx(ref_date=ref_date)

        df_portfolio = pd.merge(df_portfolio, prices, on='TICKER', how='inner')
        df_portfolio = pd.merge(df_portfolio, ticker_fx, on='TICKER', how='left')

        # Fill with 1 on local currency tickers
        df_portfolio["VALUE"].fillna(1, inplace=True)
        df_portfolio.loc[df_portfolio.FX == '#NA', "FX"] = "RON"

        df_portfolio['TOTAL_VALUE'] = df_portfolio['N_SHARES'] * df_portfolio['PRICE'] * df_portfolio['VALUE']
        df_portfolio['PROFIT'] = df_portfolio['TOTAL_VALUE'] - df_portfolio['TOTAL_COST']
        df_portfolio['PROFIT%'] = df_portfolio['PROFIT'] * 100 / df_portfolio['TOTAL_COST']

        self.df_portfolio = df_portfolio.drop_duplicates()

    def get_nav(self):
        return self.df_portfolio.TOTAL_VALUE.sum()
    
    def get_cost(self):
        return self.df_portfolio.TOTAL_COST.sum()
    
    def get_profit(self):
        return self.get_nav() - self.get_cost()
    

    def get_profit_perc(self):
        if self.ref_profit:
            return (self.get_profit() - self.ref_profit) * 100 / ( self.get_cost() + 1E-24 )
        return self.get_profit() * 100 / ( self.get_cost() + 1E-24 )


    def get_profit_perc_distrib(self):
        return self.df_portfolio[['TICKER', 'PROFIT%']]

    def get_profit_distrib(self):
        return self.df_portfolio[['TICKER', 'PROFIT']]

    def get_distrib(self, hue='TICKER'):

        res_ = self.df_portfolio[['TOTAL_VALUE','TICKER', 'COUNTRY', 'FX', 'SECTOR']]

        res_ = res_.groupby(hue)['TOTAL_VALUE'].sum().reset_index()

        res_['TOTAL_VALUE'] = res_['TOTAL_VALUE'].apply(lambda x: np.round(x, 0))



        return res_

