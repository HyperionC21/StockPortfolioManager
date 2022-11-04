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