# GLOBAL IMPORTS

# PROJECT IMPORTS
from .base import DataFetcher
from .sql import queries

class MiscFetcher(DataFetcher):
    
    def __init__(self, db_conn):
        super().__init__(db_conn)

    def fetch_fst_trans(self):
        return self.fetch_query(queries.FST_TICKER_TRANS_QUERY).FST_BUY_DT[0]

    def fetch_portfolio_composition(self, portfolio_id : int, ref_date : str):
        return self.fetch_query(queries.PORTFOLIO_COMP_QUERY.format(ref_date, ref_date))

    def fetch_last_trans_on_ticker(self, ticker, cnt):
        res_ = self.fetch_query(queries.LAST_TRANS_TICKER.format(ticker, cnt))
        return res_
    
    def fetch_dividend_amt(self, start_dt, end_dt):
        res_ = self.fetch_query(queries.DIVIDEND_AMT_QUERY.format(start_dt, end_dt)).values[0][0]
        if res_ is None:
            return 0
        return res_
