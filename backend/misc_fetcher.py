# GLOBAL IMPORTS

# PROJECT IMPORTS
from .base import DataFetcher
from .sql import queries
from .api import PortfolioStats
from utils import utils

class MiscFetcher(DataFetcher):
    
    def __init__(self, db_conn):
        super().__init__(db_conn)

    def fetch_security_src(self, ticker):
        res_ = self.fetch_query(queries.SECURITY_DATA_SOURCE.format(ticker)).values[0][0]
        return res_
    
    def fetch_fst_trans_on_filter(self, filter, filter_kind):
        res_ = self.fetch_query(queries.FST_TRANS_ON_FILTER.format(filter=filter, filter_kind=filter_kind))['DATE'][0]
        return res_

    def fetch_security_equity_gain_amt(self, ticker, ref_dt):
        res_ = PortfolioStats(db_path=self.db_conn.db_path, ref_date=utils.date2str(utils.datetime.now()), filter_kind='TICKER', filters=ticker).get_profit()
        print(res_)
        return res_

    def fetch_security_equity_amt(self, ticker, ref_dt):
        res_ = PortfolioStats(db_path=self.db_conn.db_path, ref_date=utils.date2str(utils.datetime.now()), filter_kind='TICKER', filters=ticker).get_nav()
        return res_

    def fetch_security_cost_basis_amt(self, ticker):
        res_ = self.fetch_query(queries.SECURITY_COST_BASIS_VAL.format(ticker))
        return res_

    def fetch_security_dividend_amt(self, ticker):
        res_ = self.fetch_query(queries.SECURITY_DIV_VAL.format(ticker))
        return res_

    def fetch_fst_trans(self):
        return self.fetch_query(queries.FST_TICKER_TRANS_QUERY).FST_BUY_DT[0]

    def fetch_portfolio_composition(self, portfolio_id : int, ref_date : str):
        return self.fetch_query(queries.PORTFOLIO_COMP_QUERY.format(ref_date, ref_date))

    def fetch_fst_trans_on_ticker(self, ticker, cnt):
        res_ = self.fetch_query(queries.FST_TRANS_TICKER.format(ticker, cnt)).iloc[0]
        return res_
    
    def fetch_last_trans_on_ticker(self, ticker, cnt):
        res_ = self.fetch_query(queries.F.format(ticker, cnt))
        return res_
    
    def fetch_last_div_on_ticker(self, ticker, cnt):
        res_ = self.fetch_query(queries.LAST_DIVIDEND_TICKER.format(ticker, cnt))
        return res_
    
    def fetch_dividend_amt(self, start_dt, end_dt):
        res_ = self.fetch_query(queries.DIVIDEND_AMT_QUERY.format(start_dt, end_dt))
        return res_

    def fetch_activity(self, ticker, filter_kind='TICKER'):
        if ticker == 'ALL':
            where_condition = '1 = 1'
        else:
            where_condition = f"{filter_kind} = '{ticker}'"
        print(queries.ACTIVITY_QUERY.format(where_condition))
        res_ = self.fetch_query(queries.ACTIVITY_QUERY.format(where_condition))
        return res_
