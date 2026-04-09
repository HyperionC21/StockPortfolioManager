# GLOBAL IMPORTS

# PROJECT IMPORTS
from .base import DataFetcher
from .sql import queries
from .api import PortfolioStats
from utils import utils


ALLOWED_FILTER_KINDS = {'TICKER', 'COUNTRY', 'SECTOR', 'FX', 'MARKET', 'SRC'}

class MiscFetcher(DataFetcher):
    
    def __init__(self, db_conn):
        super().__init__(db_conn)

    def _validate_filter_kind(self, filter_kind):
        if filter_kind not in ALLOWED_FILTER_KINDS:
            raise ValueError(f'Invalid filter_kind: {filter_kind}')
        return filter_kind

    def fetch_security_src(self, ticker):
        query = '''
            SELECT SRC
            FROM `SECURITY`
            WHERE TICKER = ?
        '''
        res_ = self.fetch_query(query, params=(ticker,)).values[0][0]
        return res_
    
    def fetch_fst_trans_on_filter(self, filter, filter_kind):
        filter_kind = self._validate_filter_kind(filter_kind)
        query = f'''
            SELECT
                MIN(DATE(trans.DATE)) as DATE
            FROM
                `TRANSACTION` trans
            INNER JOIN
                `SECURITY` sec ON trans.TICKER = sec.TICKER
            WHERE
                sec.{filter_kind} = ?
        '''
        res_ = self.fetch_query(query, params=(filter,))['DATE'][0]
        return res_

    def fetch_security_equity_gain_amt(self, ticker, ref_dt):
        res_ = PortfolioStats(db_path=self.db_conn.db_path, ref_date=utils.date2str(utils.datetime.now()), filter_kind='TICKER', filters=ticker).get_profit()
        print(res_)
        return res_

    def fetch_security_equity_amt(self, ticker, ref_dt):
        res_ = PortfolioStats(db_path=self.db_conn.db_path, ref_date=utils.date2str(utils.datetime.now()), filter_kind='TICKER', filters=ticker).get_nav()
        return res_

    def fetch_security_cost_basis_amt(self, ticker):
        query = '''
            SELECT
                SUM(AMOUNT * PRICE * FX) + SUM(FEE * FX)
            FROM
                `TRANSACTION`
            WHERE TICKER = ?
        '''
        res_ = self.fetch_query(query, params=(ticker,))
        return res_

    def fetch_security_dividend_amt(self, ticker):
        query = '''
            SELECT
                SUM(AMOUNT * FX)
            FROM
                `DIVIDEND`
            WHERE TICKER = ?
        '''
        res_ = self.fetch_query(query, params=(ticker,))
        return res_

    def fetch_fst_trans(self):
        return self.fetch_query(queries.FST_TICKER_TRANS_QUERY).FST_BUY_DT[0]

    def fetch_portfolio_composition(self, portfolio_id : int, ref_date : str):
        query = '''
            SELECT
                t1.TICKER,
                t2.SECTOR,
                t2.COUNTRY,
                t2.FX,
                SUM(t1.FEE * t1.FX) as TOTAL_FEE,
                SUM(t1.AMOUNT) as N_SHARES,
                SUM(t1.AMOUNT * t1.PRICE * t1.FX) as TOTAL_COST,
                ? as DT
            FROM
                'TRANSACTION' as t1
            INNER JOIN
                'SECURITY' as t2
            ON
                t1.TICKER = t2.TICKER
            WHERE
                1 = 1
                AND DATE(t1.DATE) <= DATE(?)
            GROUP BY
                t1.TICKER
        '''
        return self.fetch_query(query, params=(ref_date, ref_date))

    def fetch_fst_trans_on_ticker(self, ticker, cnt):
        cnt = int(cnt)
        query = '''
            SELECT 
                TICKER,
                DATE,
                AMOUNT as N_SHARES
            FROM `TRANSACTION`
            WHERE TICKER = ?
            ORDER BY DATE ASC
            LIMIT ?
        '''
        res_ = self.fetch_query(query, params=(ticker, cnt)).iloc[0]
        return res_
    
    def fetch_last_trans_on_ticker(self, ticker, cnt):
        cnt = int(cnt)
        query = '''
            SELECT 
                TICKER,
                DATE,
                AMOUNT as N_SHARES
            FROM `TRANSACTION`
            WHERE TICKER = ?
            ORDER BY DATE DESC
            LIMIT ?
        '''
        res_ = self.fetch_query(query, params=(ticker, cnt))
        return res_
    
    def fetch_last_div_on_ticker(self, ticker, cnt):
        cnt = int(cnt)
        query = '''
            SELECT 
                TICKER,
                DATE,
                AMOUNT as AMT
            FROM `DIVIDEND`
            WHERE TICKER = ?
            ORDER BY DATE DESC
            LIMIT ?
        '''
        res_ = self.fetch_query(query, params=(ticker, cnt))
        return res_
    
    def fetch_dividend_amt(self, start_dt, end_dt):
        query = '''
            SELECT
                div.AMOUNT * div.FX as AMT,
                div.DATE,
                sec.*
            FROM
                `DIVIDEND` div
            INNER JOIN
                `SECURITY` sec ON div.TICKER = sec.TICKER
            WHERE
                1 = 1
                AND DATE(div.DATE) >= DATE(?) AND DATE(div.DATE) <= DATE(?)
        '''
        res_ = self.fetch_query(query, params=(start_dt, end_dt))
        return res_

    def fetch_activity(self, ticker, filter_kind='TICKER'):
        filter_kind = self._validate_filter_kind(filter_kind)
        params = None
        if ticker == 'ALL':
            where_condition = '1 = 1'
        else:
            where_condition = f'{filter_kind} = ?'
            params = (ticker,)
        res_ = self.fetch_query(queries.ACTIVITY_QUERY.format(where_condition), params=params)
        return res_
