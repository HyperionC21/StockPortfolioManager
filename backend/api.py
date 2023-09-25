from datetime import datetime, timedelta
import imp
import pandas as pd
import numpy as np
from . import fx_fetcher, misc_fetcher, ticker_fetcher, base
from utils import utils



class PortfolioStats:
    def __init__(self, db_path, ref_date, filters=None, filter_kind=None, ref_profit=None, ref_cost=None) -> None:
        self.db_conn = base.BaseDBConnector(db_path)
        self.fx_fetcher = fx_fetcher.FxFetcher(self.db_conn)
        self.misc_fetcher = misc_fetcher.MiscFetcher(self.db_conn)
        self.ticker_fetcher = ticker_fetcher.TickerFetcher(self.db_conn)

        if ref_profit:
            self.ref_profit = ref_profit
        else:
            self.ref_profit = 0
        self.ref_cost = ref_cost

        df_portfolio = self.misc_fetcher.fetch_portfolio_composition(1, ref_date=ref_date)
        
        if filters and filter_kind:
            try:
                df_portfolio = df_portfolio[df_portfolio[filter_kind] == filters]
            except:
                print('filter_kind: ', filter_kind)
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

        self.df_portfolio = df_portfolio.drop_duplicates(subset=['TICKER', 'COUNTRY'])
        

    def get_fee(self):
        return self.df_portfolio.TOTAL_FEE.sum()

    def get_nav(self):
        return self.df_portfolio.TOTAL_VALUE.sum()
    
    def get_cost(self):
        return self.df_portfolio.TOTAL_COST.sum()
    
    def get_profit(self):
        return (self.get_nav() - self.get_cost() - self.get_fee()) - self.ref_profit
    
    def get_security_info(self, ticker, hue = 'TICKER'):
        if hue == 'TICKER':
            return self.df_portfolio[self.df_portfolio.TICKER == ticker].to_dict(orient='records')
        elif hue in ('COUNTRY', 'FX', 'SECTOR'):
            df_aux = self.df_portfolio[self.df_portfolio[hue] == ticker]
            df_aux = df_aux.groupby(hue)
            df_aux = df_aux.agg({
                'TOTAL_VALUE' : ['sum'],
                'PROFIT' : ['sum']
            }).reset_index()
            df_aux.columns = list(map(lambda x: x[0], df_aux.columns))
            df_aux['PROFIT%'] = df_aux['PROFIT'] * 100 / df_aux['TOTAL_VALUE']
            df_aux['COUNTRY'] = ''
            return df_aux.to_dict(orient='records')


    def get_profit_perc(self):
        ref_cost = self.ref_cost if self.ref_cost else self.get_cost()
        ref_profit = self.ref_profit if self.ref_profit else 0

        return np.round((self.get_nav() - (self.get_cost() + self.get_fee() + ref_profit)) * 100 / ( ref_cost + 1E-24 ), 1)


    def get_profit_perc_distrib(self):
        return self.df_portfolio[['TICKER', 'PROFIT%']]

    def get_profit_distrib(self):
        return self.df_portfolio[['TICKER', 'PROFIT']]

    def get_distrib(self, hue='TICKER'):

        res_ = self.df_portfolio[['TOTAL_VALUE','TICKER', 'COUNTRY', 'FX', 'SECTOR']]


        res_ = res_.groupby(hue)['TOTAL_VALUE'].sum().reset_index()

        res_['TOTAL_VALUE'] = res_['TOTAL_VALUE'].apply(lambda x: np.round(x, 0))

        res_ = res_.rename(columns={
            'TOTAL_VALUE' : 'VALUE',
            hue : 'LABEL'
        })

        return res_

class Period:
    PERIOD_SIZE_MAP = {
        'M' : timedelta(days=30),
        'Y' : timedelta(days=365),
        'W' : timedelta(days=7),
        'Q' : timedelta(days=90)
    }

    MISC_PERIODS = {'YTD', 'ALL'}

    def __init__(self, period: str, ref_dt: datetime=None, portfolio_start_dt: datetime=None) -> None:
        import re
        REGEX = r'(\d+)(\w+)'
        
        ref_dt = utils.str2date(ref_dt)

        if period not in Period.MISC_PERIODS:
            self.frame_size = re.search(REGEX, period).group(1)
            self.period_size = Period.PERIOD_SIZE_MAP.get(re.search(REGEX, period).group(2))
            self.delta = int(self.frame_size) * self.period_size
        else:
            if period == 'YTD':
                start_dt = ref_dt.replace(month=1, day=1)
                self.delta = ref_dt - start_dt
            elif period == 'ALL':
                start_dt = utils.str2date(portfolio_start_dt)
                self.delta = ref_dt - start_dt
        assert isinstance(self.delta, timedelta)




    

class Metric:
    def __init__(self, name, db_path, period, ref_dt) -> None:
        self.ref_dt = utils.date2str(datetime.now()) if not ref_dt else ref_dt
        portfolio_start_dt = None
        if period == 'ALL' and db_path is not None:
            db_conn = base.BaseDBConnector(db_path)
            misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)
            portfolio_start_dt = misc_fetcher_.fetch_fst_trans()
        
        print('portfolio_start_dt: ', portfolio_start_dt)
        self.period = Period(period, self.ref_dt, portfolio_start_dt)

        self.db_path = db_path
        
    
    def get_name(self):
        return self.name
    
    def compute(self):
        raise NotImplementedError

class Nav(Metric):
    def __init__(self, db_path, period, filters=None, filter_kind=None, ref_dt=None) -> None:
        super().__init__('nav', db_path, period, ref_dt)
        self.filters = filters
        self.filter_kind = filter_kind
    def compute(self):
        return np.round(PortfolioStats(self.db_path, self.ref_dt, self.filters, self.filter_kind).get_nav())

class CostBasis(Metric):
    def __init__(self, db_path, period, filters=None, filter_kind=None, ref_dt=None) -> None:
        super().__init__('cost_basis', db_path, period, ref_dt)
        self.filters = filters
        self.filter_kind = filter_kind
    def compute(self):
        return np.round(PortfolioStats(self.db_path, self.ref_dt, self.filters, self.filter_kind).get_cost())

class Fee(Metric):
     def __init__(self, db_path, period, ref_dt=None) -> None:
        super().__init__('fee', db_path, period, ref_dt)
    
     def compute(self):
        return np.round(PortfolioStats(self.db_path, self.ref_dt).get_fee()) 

class PeriodProfitVal(Metric):
    def __init__(self, db_path, period, ref_dt=None) -> None:
        super().__init__('periodprofitval', db_path, period, ref_dt)

    def compute(self):
        start_dt = utils.str2date(self.ref_dt) - self.period.delta
        start_dt = utils.date2str(start_dt)

        start_profit = PortfolioStats(self.db_path, start_dt).get_profit()
        end_profit = PortfolioStats(self.db_path, self.ref_dt).get_profit()

        profit = end_profit - start_profit
        n_days = self.period.delta.total_seconds() / ( 3600 * 24)

        annualized_profit = profit * 365 / n_days

        return annualized_profit

class PeriodProfitPerc(Metric):
    def __init__(self, db_path, period, ref_dt=None) -> None:
        super().__init__('periodprofitperc', db_path, period, ref_dt)

    def compute(self):
        start_dt = utils.str2date(self.ref_dt) - self.period.delta
        start_dt = utils.date2str(start_dt)

        start_profit = PortfolioStats(self.db_path, start_dt).get_profit()
        end_profit = PortfolioStats(self.db_path, self.ref_dt).get_profit()

        profit = end_profit - start_profit
        n_days = self.period.delta.total_seconds() / ( 3600 * 24)

        annualized_profit = profit * 365 / n_days
        ref_cost = PortfolioStats(self.db_path, self.ref_dt).get_cost()

        return  np.round(annualized_profit * 100 / (ref_cost + 1E-24), 2)

class Profit(Metric):
    def __init__(self, db_path, period, ref_dt=None) -> None:
        super().__init__('profit', db_path, period, ref_dt)
    def compute(self):

        start_dt = utils.str2date(self.ref_dt) - self.period.delta
        start_dt = utils.date2str(start_dt)
        
        ref_profit = PortfolioStats(self.db_path, start_dt).get_profit()

        return np.round(PortfolioStats(self.db_path, self.ref_dt, ref_profit=ref_profit).get_profit())

class DivYield(Metric):
    def __init__(self,db_path, period, ref_dt=None) -> None:
        super().__init__('div_yield', db_path, period, ref_dt)
    
    def _compute_amt(self):
        db_conn = base.BaseDBConnector(self.db_path)
        fetcher = misc_fetcher.MiscFetcher(db_conn=db_conn)

        end_dt = self.ref_dt
        start_dt = utils.str2date(end_dt) - self.period.delta
        start_dt = utils.date2str(start_dt)

        return fetcher.fetch_dividend_amt(start_dt=start_dt, end_dt=end_dt)

    def _compute_avg_portfolio_nav(self):
        start_dt = utils.str2date(self.ref_dt) - self.period.delta
        start_dt = utils.date2str(start_dt)

        date_range = utils.daterange(start_dt, self.ref_dt, step=30)
        navs = list(map(lambda x: PortfolioStats(self.db_path, x).get_nav(), date_range))
        return np.mean(navs)

    def compute(self):
        div_amt = self._compute_amt()
        avg_port_nav = self._compute_avg_portfolio_nav()
        print(div_amt, avg_port_nav)
        return np.round(div_amt / (avg_port_nav + 1E-24), 4)


class DivVal(Metric):
    def __init__(self, db_path, period, filters=None, filter_kind=None, ref_dt=None) -> None:
        super().__init__('div_val', db_path, period, ref_dt)
        self.filters = filters
        self.filter_kind = filter_kind

    def compute(self):
        db_conn = base.BaseDBConnector(self.db_path)
        fetcher = misc_fetcher.MiscFetcher(db_conn=db_conn)

        end_dt = self.ref_dt
        start_dt = utils.str2date(end_dt) - self.period.delta
        start_dt = utils.date2str(start_dt)

        #return np.round(fetcher.fetch_dividend_amt(start_dt=start_dt, end_dt=end_dt))
        df_divs = fetcher.fetch_dividend_amt(start_dt=start_dt, end_dt=end_dt)
        if self.filters is not None and self.filter_kind is not None:
            df_divs = df_divs[df_divs[self.filter_kind] == self.filters]
        
        return df_divs['AMT'].sum()
        

class DivSecurity(Metric):
    def __init__(self, ticker, db_path) -> None:
        self.ticker = ticker
        self.db_path = db_path

    def compute(self):
        db_conn = base.BaseDBConnector(self.db_path)
        fetcher = misc_fetcher.MiscFetcher(db_conn=db_conn)

        try:
            res_ = np.round(fetcher.fetch_security_dividend_amt(self.ticker).values[0][0], 2)
        except:
            res_ = 0
        return res_

class PE(Metric):
    def __init__(self, ticker, db_path) -> None:
        self.ticker = ticker
        db_conn = base.BaseDBConnector(db_path)
        fetcher = misc_fetcher.MiscFetcher(db_conn=db_conn)

        self.src = fetcher.fetch_security_src(ticker)
    
    def compute(self):
        try:
            if self.src == 'YF':
                ticker = base.yf.Ticker(self.ticker)
                ticker_info = ticker.info
                return np.round(ticker_info.get('forwardPE', 'N/A'), 2)
            elif self.src == 'BVB':
                return np.round(float(ticker_fetcher.get_security_pe_bvb(self.ticker)), 2)
            else:
                return 'N/A'
        except:
            return 'N/A'

class CostBasisSecurity(Metric):
    def __init__(self, ticker, db_path) -> None:
        self.ticker = ticker
        self.db_path = db_path

    def compute(self):
        db_conn = base.BaseDBConnector(self.db_path)
        fetcher = misc_fetcher.MiscFetcher(db_conn=db_conn)

        try:
            res_ = np.clip(np.round(fetcher.fetch_security_cost_basis_amt(self.ticker).values[0][0], 2), a_min=0, a_max=None)
        except Exception as e:
            print('Error::', e)
            res_ = 0
        return res_

class EquityGainSecurity(Metric):
    def __init__(self, ticker, ref_dt, db_path) -> None:
        self.ticker = ticker
        self.db_path = db_path
        self.ref_dt = ref_dt

    def compute(self):
        db_conn = base.BaseDBConnector(self.db_path)
        fetcher = misc_fetcher.MiscFetcher(db_conn=db_conn)
        try:
            res_ = np.round(fetcher.fetch_security_equity_gain_amt(self.ticker, self.ref_dt), 2)
        except Exception as e:
            print('Error::', e)
            res_ = 0
        return res_


class EquityAmtSecurity(Metric):
    def __init__(self, ticker, ref_dt, db_path) -> None:
        self.ticker = ticker
        self.db_path = db_path
        self.ref_dt = ref_dt

    def compute(self):
        db_conn = base.BaseDBConnector(self.db_path)
        fetcher = misc_fetcher.MiscFetcher(db_conn=db_conn)
        try:
            res_ = np.round(fetcher.fetch_security_equity_amt(self.ticker, self.ref_dt), 2)
        except Exception as e:
            print('Error::', e)
            res_ = 0
        return res_