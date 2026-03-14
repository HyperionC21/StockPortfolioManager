"""
Portfolio Benchmarks, Risk Metrics, and Strategy Analytics.

Provides:
- Benchmark comparison (vs SPY, STOXX600, custom indices)
- Risk metrics: Sharpe, Sortino, Max Drawdown, Volatility, Calmar, Beta, Alpha
- Diversification: Herfindahl Index, correlation matrix
- Strategy: rebalancing suggestions, dividend growth analysis
- Investment insights: portfolio health score, risk-adjusted rankings
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from . import base, misc_fetcher, ticker_fetcher, fx_fetcher
from .api import PortfolioStats
from utils import utils

# Annualized risk-free rate (approximate 10Y government bond yield)
DEFAULT_RISK_FREE_RATE = 0.04

# Common benchmark tickers
BENCHMARKS = {
    'SPY': 'S&P 500',
    'QQQ': 'NASDAQ 100',
    'IWM': 'Russell 2000',
    'VT': 'Total World Stock',
    'EFA': 'MSCI EAFE (Developed ex-US)',
    'EEM': 'MSCI Emerging Markets',
    'AGG': 'US Aggregate Bond',
    'GLD': 'Gold',
}


class PortfolioBenchmark:
    """Compare portfolio performance against benchmark indices."""

    def __init__(self, db_path, start_date=None, end_date=None, step=7,
                 filters=None, filter_kind=None):
        self.db_path = db_path
        self.db_conn = base.BaseDBConnector(db_path)
        self.misc_fetcher = misc_fetcher.MiscFetcher(self.db_conn)
        self.ticker_fetcher = ticker_fetcher.TickerFetcher(self.db_conn)
        self.fx_fetcher = fx_fetcher.FxFetcher(self.db_conn)

        self.end_date = end_date or utils.date2str(datetime.now())
        self.start_date = start_date or self.misc_fetcher.fetch_fst_trans()
        self.step = step
        self.filters = filters
        self.filter_kind = filter_kind

    def _get_portfolio_nav_series(self):
        """Build a time series of portfolio NAV values."""
        date_range = list(utils.daterange(self.start_date, self.end_date, self.step))
        navs = []
        for dt in date_range:
            dt_str = utils.date2str(dt) if isinstance(dt, datetime) else dt
            try:
                ps = PortfolioStats(self.db_path, dt_str,
                                    self.filters, self.filter_kind)
                navs.append({'date': dt_str, 'nav': ps.get_nav()})
            except Exception:
                continue

        df = pd.DataFrame(navs)
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date').sort_index()
        return df

    def _get_benchmark_prices(self, benchmark_ticker):
        """Fetch benchmark prices from Yahoo Finance for the date range."""
        try:
            ticker = base.yf.Ticker(benchmark_ticker)
            df = ticker.history(start=self.start_date, end=self.end_date)
            if df.empty:
                return pd.DataFrame()
            df = df[['Close']].rename(columns={'Close': 'price'})
            df.index = df.index.tz_localize(None)
            return df
        except Exception:
            return pd.DataFrame()

    def compare_performance(self, benchmark_ticker='SPY'):
        """
        Compare portfolio cumulative return vs a benchmark.

        Returns dict with:
        - dates: list of date strings
        - portfolio_return: cumulative return % series
        - benchmark_return: cumulative return % series
        - portfolio_total_return: final cumulative return %
        - benchmark_total_return: final cumulative return %
        - outperformance: portfolio minus benchmark (alpha estimate)
        """
        nav_df = self._get_portfolio_nav_series()
        bench_df = self._get_benchmark_prices(benchmark_ticker)

        if nav_df.empty or bench_df.empty:
            return {'error': 'Insufficient data for comparison'}

        # Align dates
        nav_df = nav_df.resample('W-FRI').last().dropna()
        bench_df = bench_df.resample('W-FRI').last().dropna()

        common_idx = nav_df.index.intersection(bench_df.index)
        if len(common_idx) < 2:
            return {'error': 'Not enough overlapping dates'}

        nav_aligned = nav_df.loc[common_idx]
        bench_aligned = bench_df.loc[common_idx]

        port_ret = (nav_aligned['nav'] / nav_aligned['nav'].iloc[0] - 1) * 100
        bench_ret = (bench_aligned['price'] / bench_aligned['price'].iloc[0] - 1) * 100

        return {
            'benchmark': benchmark_ticker,
            'benchmark_name': BENCHMARKS.get(benchmark_ticker, benchmark_ticker),
            'dates': [d.strftime('%Y-%m-%d') for d in common_idx],
            'portfolio_return': port_ret.round(2).tolist(),
            'benchmark_return': bench_ret.round(2).tolist(),
            'portfolio_total_return': round(float(port_ret.iloc[-1]), 2),
            'benchmark_total_return': round(float(bench_ret.iloc[-1]), 2),
            'outperformance': round(float(port_ret.iloc[-1] - bench_ret.iloc[-1]), 2),
        }

    def multi_benchmark_comparison(self, benchmarks=None):
        """Compare portfolio against multiple benchmarks at once."""
        benchmarks = benchmarks or ['SPY', 'QQQ', 'AGG']
        results = []
        for b in benchmarks:
            comp = self.compare_performance(b)
            if 'error' not in comp:
                results.append({
                    'benchmark': b,
                    'name': BENCHMARKS.get(b, b),
                    'benchmark_return': comp['benchmark_total_return'],
                    'portfolio_return': comp['portfolio_total_return'],
                    'outperformance': comp['outperformance'],
                })
        return results


class RiskMetrics:
    """
    Compute risk-adjusted performance metrics for the portfolio.

    All return calculations use weekly sampling to balance accuracy and speed.
    """

    def __init__(self, db_path, start_date=None, end_date=None, step=7,
                 risk_free_rate=DEFAULT_RISK_FREE_RATE,
                 filters=None, filter_kind=None):
        self.db_path = db_path
        self.db_conn = base.BaseDBConnector(db_path)
        self.misc_fetcher = misc_fetcher.MiscFetcher(self.db_conn)
        self.risk_free_rate = risk_free_rate

        self.end_date = end_date or utils.date2str(datetime.now())
        self.start_date = start_date or self.misc_fetcher.fetch_fst_trans()
        self.step = step
        self.filters = filters
        self.filter_kind = filter_kind

        self._nav_series = None
        self._returns = None

    def _get_nav_series(self):
        """Cached NAV series."""
        if self._nav_series is not None:
            return self._nav_series

        date_range = list(utils.daterange(self.start_date, self.end_date, self.step))
        navs = []
        for dt in date_range:
            dt_str = utils.date2str(dt) if isinstance(dt, datetime) else dt
            try:
                ps = PortfolioStats(self.db_path, dt_str,
                                    self.filters, self.filter_kind)
                navs.append({'date': dt_str, 'nav': ps.get_nav()})
            except Exception:
                continue

        self._nav_series = pd.DataFrame(navs)
        if len(self._nav_series) > 0:
            self._nav_series['date'] = pd.to_datetime(self._nav_series['date'])
            self._nav_series = self._nav_series.set_index('date').sort_index()
        return self._nav_series

    def _get_returns(self):
        """Cached periodic returns."""
        if self._returns is not None:
            return self._returns
        nav = self._get_nav_series()
        if nav.empty or len(nav) < 2:
            self._returns = pd.Series(dtype=float)
        else:
            self._returns = nav['nav'].pct_change().dropna()
        return self._returns

    def volatility(self):
        """Annualized portfolio volatility (standard deviation of returns)."""
        returns = self._get_returns()
        if returns.empty:
            return None
        periods_per_year = 365 / self.step
        return round(float(returns.std() * np.sqrt(periods_per_year)) * 100, 2)

    def sharpe_ratio(self):
        """
        Annualized Sharpe Ratio = (annualized return - risk-free rate) / annualized vol.
        """
        returns = self._get_returns()
        if returns.empty or len(returns) < 2:
            return None

        periods_per_year = 365 / self.step
        ann_return = (1 + returns.mean()) ** periods_per_year - 1
        ann_vol = returns.std() * np.sqrt(periods_per_year)

        if ann_vol == 0:
            return None
        return round(float((ann_return - self.risk_free_rate) / ann_vol), 2)

    def sortino_ratio(self):
        """
        Sortino Ratio — like Sharpe but uses only downside deviation.
        Penalizes negative volatility only.
        """
        returns = self._get_returns()
        if returns.empty or len(returns) < 2:
            return None

        periods_per_year = 365 / self.step
        ann_return = (1 + returns.mean()) ** periods_per_year - 1
        downside = returns[returns < 0]

        if downside.empty or downside.std() == 0:
            return None
        downside_dev = downside.std() * np.sqrt(periods_per_year)
        return round(float((ann_return - self.risk_free_rate) / downside_dev), 2)

    def max_drawdown(self):
        """
        Maximum Drawdown — largest peak-to-trough decline in portfolio value.
        Returns a dict with drawdown %, peak date, and trough date.
        """
        nav = self._get_nav_series()
        if nav.empty or len(nav) < 2:
            return None

        cummax = nav['nav'].cummax()
        drawdown = (nav['nav'] - cummax) / cummax

        trough_idx = drawdown.idxmin()
        peak_idx = nav['nav'][:trough_idx].idxmax()

        return {
            'max_drawdown_pct': round(float(drawdown.min()) * 100, 2),
            'peak_date': peak_idx.strftime('%Y-%m-%d'),
            'trough_date': trough_idx.strftime('%Y-%m-%d'),
            'peak_value': round(float(nav['nav'][peak_idx]), 2),
            'trough_value': round(float(nav['nav'][trough_idx]), 2),
        }

    def calmar_ratio(self):
        """
        Calmar Ratio = annualized return / |max drawdown|.
        Higher is better — measures return per unit of drawdown risk.
        """
        returns = self._get_returns()
        dd = self.max_drawdown()
        if returns.empty or dd is None or dd['max_drawdown_pct'] == 0:
            return None

        periods_per_year = 365 / self.step
        ann_return = ((1 + returns.mean()) ** periods_per_year - 1) * 100
        return round(float(ann_return / abs(dd['max_drawdown_pct'])), 2)

    def beta(self, benchmark_ticker='SPY'):
        """
        Portfolio Beta vs a benchmark.
        Beta > 1 means more volatile than market; < 1 means less.
        """
        returns = self._get_returns()
        if returns.empty:
            return None

        try:
            bench = base.yf.Ticker(benchmark_ticker)
            bench_df = bench.history(start=self.start_date, end=self.end_date)
            if bench_df.empty:
                return None
            bench_df.index = bench_df.index.tz_localize(None)
            bench_returns = bench_df['Close'].resample(f'{self.step}D').last().pct_change().dropna()
        except Exception:
            return None

        # Align
        common = returns.index.intersection(bench_returns.index)
        if len(common) < 5:
            # Try aligning by nearest date
            port_weekly = returns.resample('W-FRI').last().dropna()
            bench_weekly = bench_returns.resample('W-FRI').last().dropna()
            common = port_weekly.index.intersection(bench_weekly.index)
            if len(common) < 5:
                return None
            r_p = port_weekly.loc[common]
            r_b = bench_weekly.loc[common]
        else:
            r_p = returns.loc[common]
            r_b = bench_returns.loc[common]

        covar = np.cov(r_p.values, r_b.values)
        if covar[1, 1] == 0:
            return None
        return round(float(covar[0, 1] / covar[1, 1]), 2)

    def alpha(self, benchmark_ticker='SPY'):
        """
        Jensen's Alpha = portfolio return - [Rf + Beta * (Rm - Rf)].
        Positive alpha means outperformance after adjusting for risk.
        """
        returns = self._get_returns()
        b = self.beta(benchmark_ticker)
        if returns.empty or b is None:
            return None

        try:
            bench = base.yf.Ticker(benchmark_ticker)
            bench_df = bench.history(start=self.start_date, end=self.end_date)
            bench_df.index = bench_df.index.tz_localize(None)
            bench_returns = bench_df['Close'].pct_change().dropna()
        except Exception:
            return None

        periods_per_year = 365 / self.step
        ann_port_return = (1 + returns.mean()) ** periods_per_year - 1
        ann_bench_return = (1 + bench_returns.mean()) ** 252 - 1  # daily -> annual

        jensen_alpha = ann_port_return - (self.risk_free_rate + b * (ann_bench_return - self.risk_free_rate))
        return round(float(jensen_alpha) * 100, 2)

    def treynor_ratio(self, benchmark_ticker='SPY'):
        """
        Treynor Ratio = (portfolio return - Rf) / Beta.
        Measures return per unit of systematic risk.
        """
        returns = self._get_returns()
        b = self.beta(benchmark_ticker)
        if returns.empty or b is None or b == 0:
            return None

        periods_per_year = 365 / self.step
        ann_return = (1 + returns.mean()) ** periods_per_year - 1
        return round(float((ann_return - self.risk_free_rate) / b), 4)

    def compute_all(self, benchmark_ticker='SPY'):
        """Compute all risk metrics at once."""
        return {
            'volatility_pct': self.volatility(),
            'sharpe_ratio': self.sharpe_ratio(),
            'sortino_ratio': self.sortino_ratio(),
            'max_drawdown': self.max_drawdown(),
            'calmar_ratio': self.calmar_ratio(),
            'beta': self.beta(benchmark_ticker),
            'alpha_pct': self.alpha(benchmark_ticker),
            'treynor_ratio': self.treynor_ratio(benchmark_ticker),
            'benchmark': benchmark_ticker,
            'risk_free_rate': self.risk_free_rate,
            'period': f'{self.start_date} to {self.end_date}',
        }


class DiversificationAnalytics:
    """Analyze portfolio concentration and diversification."""

    def __init__(self, db_path, ref_date=None, filters=None, filter_kind=None):
        self.db_path = db_path
        self.ref_date = ref_date or utils.date2str(datetime.now())
        self.ps = PortfolioStats(db_path, self.ref_date, filters, filter_kind)
        self.df = self.ps.df_portfolio

    def herfindahl_index(self, hue='TICKER'):
        """
        Herfindahl-Hirschman Index (HHI) — measures portfolio concentration.
        Range: 0 to 10000.
        - < 1500: well-diversified
        - 1500-2500: moderate concentration
        - > 2500: highly concentrated
        """
        distrib = self.ps.get_distrib(hue)
        weights = distrib['VALUE'] / distrib['VALUE'].sum()
        hhi = float((weights ** 2).sum() * 10000)
        n_holdings = len(distrib)

        # Normalized HHI (0 = perfectly diversified, 1 = single holding)
        if n_holdings > 1:
            min_hhi = 10000 / n_holdings
            nhhi = (hhi - min_hhi) / (10000 - min_hhi)
        else:
            nhhi = 1.0

        return {
            'hhi': round(hhi, 0),
            'normalized_hhi': round(nhhi, 4),
            'n_holdings': n_holdings,
            'interpretation': (
                'Well diversified' if hhi < 1500 else
                'Moderately concentrated' if hhi < 2500 else
                'Highly concentrated'
            ),
            'hue': hue,
        }

    def concentration_top_n(self, n=5, hue='TICKER'):
        """What % of the portfolio is in the top N holdings?"""
        distrib = self.ps.get_distrib(hue)
        distrib = distrib.sort_values('VALUE', ascending=False)
        total = distrib['VALUE'].sum()
        top_n = distrib.head(n)
        top_pct = float(top_n['VALUE'].sum() / total * 100)

        return {
            'top_n': n,
            'concentration_pct': round(top_pct, 2),
            'holdings': top_n[['LABEL', 'VALUE']].to_dict(orient='records'),
        }

    def diversification_by_dimension(self):
        """HHI across all dimensions: ticker, country, sector, currency."""
        results = {}
        for hue in ['TICKER', 'COUNTRY', 'SECTOR', 'FX']:
            try:
                results[hue.lower()] = self.herfindahl_index(hue)
            except Exception:
                results[hue.lower()] = None
        return results

    def correlation_matrix(self, period_days=365, step=7):
        """
        Compute pairwise return correlations between portfolio holdings.
        Helps identify diversification opportunities.
        """
        tickers = self.df[self.df['N_SHARES'] > 0]['TICKER'].tolist()
        if len(tickers) < 2:
            return {'error': 'Need at least 2 holdings for correlation'}

        start_date = utils.date2str(
            utils.str2date(self.ref_date) - timedelta(days=period_days)
        )

        prices = {}
        for ticker in tickers:
            try:
                t = base.yf.Ticker(ticker)
                hist = t.history(start=start_date, end=self.ref_date)
                if not hist.empty:
                    prices[ticker] = hist['Close'].resample(f'{step}D').last().dropna()
            except Exception:
                continue

        if len(prices) < 2:
            return {'error': 'Not enough price data for correlation'}

        df_prices = pd.DataFrame(prices)
        df_returns = df_prices.pct_change().dropna()

        corr = df_returns.corr()

        # Find most and least correlated pairs
        pairs = []
        tickers_list = corr.columns.tolist()
        for i in range(len(tickers_list)):
            for j in range(i + 1, len(tickers_list)):
                pairs.append({
                    'pair': f'{tickers_list[i]}/{tickers_list[j]}',
                    'correlation': round(float(corr.iloc[i, j]), 3),
                })

        pairs.sort(key=lambda x: x['correlation'])

        return {
            'matrix': {k: {k2: round(float(v), 3) for k2, v in row.items()}
                       for k, row in corr.to_dict().items()},
            'most_correlated': pairs[-3:] if len(pairs) >= 3 else pairs,
            'least_correlated': pairs[:3] if len(pairs) >= 3 else pairs,
        }


class DividendAnalytics:
    """Analyze dividend income trends and growth."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.db_conn = base.BaseDBConnector(db_path)
        self.misc_fetcher = misc_fetcher.MiscFetcher(self.db_conn)

    def annual_dividend_summary(self):
        """Year-by-year dividend income breakdown."""
        start_dt = self.misc_fetcher.fetch_fst_trans()
        end_dt = utils.date2str(datetime.now())

        df_divs = self.misc_fetcher.fetch_dividend_amt(start_dt, end_dt)
        if df_divs.empty:
            return {'years': [], 'message': 'No dividends found'}

        df_divs['YEAR'] = pd.to_datetime(df_divs['DATE']).dt.year
        yearly = df_divs.groupby('YEAR')['AMT'].sum().reset_index()
        yearly.columns = ['year', 'total_dividends']
        yearly['total_dividends'] = yearly['total_dividends'].round(2)

        # YoY growth
        yearly['yoy_growth_pct'] = yearly['total_dividends'].pct_change() * 100
        yearly['yoy_growth_pct'] = yearly['yoy_growth_pct'].round(2)

        return {
            'years': yearly.to_dict(orient='records'),
            'total_lifetime_dividends': round(float(yearly['total_dividends'].sum()), 2),
            'avg_annual_dividends': round(float(yearly['total_dividends'].mean()), 2),
            'avg_yoy_growth_pct': round(float(yearly['yoy_growth_pct'].dropna().mean()), 2)
            if len(yearly) > 1 else None,
        }

    def dividend_by_ticker(self):
        """Total dividends received per ticker, ranked."""
        start_dt = self.misc_fetcher.fetch_fst_trans()
        end_dt = utils.date2str(datetime.now())

        df_divs = self.misc_fetcher.fetch_dividend_amt(start_dt, end_dt)
        if df_divs.empty:
            return []

        by_ticker = df_divs.groupby('TICKER')['AMT'].sum().reset_index()
        by_ticker.columns = ['ticker', 'total_dividends']
        by_ticker = by_ticker.sort_values('total_dividends', ascending=False)
        by_ticker['total_dividends'] = by_ticker['total_dividends'].round(2)

        return by_ticker.to_dict(orient='records')

    def dividend_yield_vs_cost(self):
        """
        Yield on cost — dividends received / cost basis.
        Shows actual income return on money invested.
        """
        start_dt = self.misc_fetcher.fetch_fst_trans()
        end_dt = utils.date2str(datetime.now())

        df_divs = self.misc_fetcher.fetch_dividend_amt(start_dt, end_dt)
        if df_divs.empty:
            return {'yield_on_cost': 0, 'message': 'No dividends found'}

        total_divs = df_divs['AMT'].sum()

        ps = PortfolioStats(self.db_path, end_dt)
        cost = ps.get_cost()

        if cost == 0:
            return {'yield_on_cost': 0}

        yoc = total_divs / cost * 100

        # Annualized yield on cost
        days_invested = (utils.str2date(end_dt) - utils.str2date(start_dt)).days
        if days_invested > 0:
            ann_yoc = yoc * 365 / days_invested
        else:
            ann_yoc = 0

        return {
            'yield_on_cost_pct': round(float(yoc), 2),
            'annualized_yield_on_cost_pct': round(float(ann_yoc), 2),
            'total_dividends': round(float(total_divs), 2),
            'total_cost_basis': round(float(cost), 2),
        }


class RebalancingSuggestions:
    """
    Generate portfolio rebalancing recommendations.

    Supports equal-weight and custom target allocations.
    """

    def __init__(self, db_path, ref_date=None):
        self.db_path = db_path
        self.ref_date = ref_date or utils.date2str(datetime.now())
        self.ps = PortfolioStats(db_path, self.ref_date)

    def equal_weight_rebalance(self, hue='TICKER', tolerance_pct=2.0):
        """
        Suggest trades to achieve equal weighting.

        tolerance_pct: only flag positions deviating more than this % from target.
        """
        distrib = self.ps.get_distrib(hue)
        n = len(distrib)
        if n == 0:
            return {'suggestions': [], 'message': 'No holdings found'}

        target_pct = 100.0 / n
        total_value = distrib['VALUE'].sum()
        distrib['current_pct'] = distrib['VALUE'] / total_value * 100
        distrib['target_pct'] = target_pct
        distrib['deviation_pct'] = distrib['current_pct'] - target_pct
        distrib['action_value'] = distrib['deviation_pct'] / 100 * total_value

        # Only flag significant deviations
        significant = distrib[abs(distrib['deviation_pct']) > tolerance_pct]

        suggestions = []
        for _, row in significant.iterrows():
            action = 'SELL' if row['deviation_pct'] > 0 else 'BUY'
            suggestions.append({
                'holding': row['LABEL'],
                'current_pct': round(float(row['current_pct']), 2),
                'target_pct': round(target_pct, 2),
                'deviation_pct': round(float(row['deviation_pct']), 2),
                'action': action,
                'amount': round(abs(float(row['action_value'])), 2),
            })

        suggestions.sort(key=lambda x: abs(x['deviation_pct']), reverse=True)

        return {
            'strategy': 'equal_weight',
            'target_pct': round(target_pct, 2),
            'tolerance_pct': tolerance_pct,
            'total_portfolio_value': round(float(total_value), 2),
            'suggestions': suggestions,
            'drift_score': round(float(significant['deviation_pct'].abs().mean()), 2)
            if len(significant) > 0 else 0,
        }

    def custom_target_rebalance(self, targets, hue='TICKER', tolerance_pct=2.0):
        """
        Suggest trades to match custom target allocations.

        targets: dict like {'AAPL': 20, 'GOOGL': 15, ...} (% allocations)
        """
        distrib = self.ps.get_distrib(hue)
        total_value = distrib['VALUE'].sum()
        distrib['current_pct'] = distrib['VALUE'] / total_value * 100

        suggestions = []
        for _, row in distrib.iterrows():
            label = row['LABEL']
            target = targets.get(label, 0)
            current = float(row['current_pct'])
            deviation = current - target

            if abs(deviation) > tolerance_pct:
                action = 'SELL' if deviation > 0 else 'BUY'
                suggestions.append({
                    'holding': label,
                    'current_pct': round(current, 2),
                    'target_pct': target,
                    'deviation_pct': round(deviation, 2),
                    'action': action,
                    'amount': round(abs(deviation / 100 * total_value), 2),
                })

        # Check for targets not currently held
        held = set(distrib['LABEL'].tolist())
        for label, target in targets.items():
            if label not in held and target > tolerance_pct:
                suggestions.append({
                    'holding': label,
                    'current_pct': 0,
                    'target_pct': target,
                    'deviation_pct': -target,
                    'action': 'BUY',
                    'amount': round(target / 100 * total_value, 2),
                })

        suggestions.sort(key=lambda x: abs(x['deviation_pct']), reverse=True)

        return {
            'strategy': 'custom_target',
            'tolerance_pct': tolerance_pct,
            'total_portfolio_value': round(float(total_value), 2),
            'suggestions': suggestions,
        }


class PortfolioHealthScore:
    """
    Generate an overall portfolio health score (0-100) based on multiple factors.

    Factors:
    - Diversification (HHI)
    - Risk-adjusted returns (Sharpe)
    - Drawdown resilience
    - Income generation (dividend yield)
    """

    def __init__(self, db_path, period='1Y', ref_date=None):
        self.db_path = db_path
        self.ref_date = ref_date or utils.date2str(datetime.now())
        self.period = period

    def _score_diversification(self):
        """Score 0-25 based on HHI."""
        try:
            da = DiversificationAnalytics(self.db_path, self.ref_date)
            hhi = da.herfindahl_index()['hhi']
            # HHI 10000 (1 stock) -> 0 points, HHI < 1000 -> 25 points
            score = max(0, min(25, 25 * (1 - hhi / 5000)))
            return round(score, 1)
        except Exception:
            return 0

    def _score_risk_return(self):
        """Score 0-25 based on Sharpe ratio."""
        try:
            start = utils.date2str(utils.str2date(self.ref_date) - timedelta(days=365))
            rm = RiskMetrics(self.db_path, start, self.ref_date)
            sharpe = rm.sharpe_ratio()
            if sharpe is None:
                return 0
            # Sharpe < 0 -> 0 points, Sharpe >= 2 -> 25 points
            score = max(0, min(25, sharpe * 12.5))
            return round(score, 1)
        except Exception:
            return 0

    def _score_drawdown(self):
        """Score 0-25 based on max drawdown."""
        try:
            start = utils.date2str(utils.str2date(self.ref_date) - timedelta(days=365))
            rm = RiskMetrics(self.db_path, start, self.ref_date)
            dd = rm.max_drawdown()
            if dd is None:
                return 12.5
            mdd = abs(dd['max_drawdown_pct'])
            # MDD 0% -> 25 points, MDD >= 50% -> 0 points
            score = max(0, min(25, 25 * (1 - mdd / 50)))
            return round(score, 1)
        except Exception:
            return 0

    def _score_income(self):
        """Score 0-25 based on dividend yield."""
        try:
            da = DividendAnalytics(self.db_path)
            yoc = da.dividend_yield_vs_cost()
            ann_yoc = yoc.get('annualized_yield_on_cost_pct', 0)
            # 0% yield -> 5 points (not holding divs is ok), >= 5% -> 25 points
            score = max(5, min(25, 5 + ann_yoc * 4))
            return round(score, 1)
        except Exception:
            return 5

    def compute(self):
        """Compute overall health score with component breakdown."""
        diversification = self._score_diversification()
        risk_return = self._score_risk_return()
        drawdown = self._score_drawdown()
        income = self._score_income()

        total = diversification + risk_return + drawdown + income

        if total >= 80:
            grade = 'A'
            summary = 'Excellent — well-diversified with strong risk-adjusted returns'
        elif total >= 65:
            grade = 'B'
            summary = 'Good — solid portfolio with room for minor improvements'
        elif total >= 50:
            grade = 'C'
            summary = 'Average — consider improving diversification or risk management'
        elif total >= 35:
            grade = 'D'
            summary = 'Below average — significant concentration or volatility risks'
        else:
            grade = 'F'
            summary = 'Needs attention — high risk, poor diversification, or negative returns'

        return {
            'total_score': round(total, 1),
            'grade': grade,
            'summary': summary,
            'components': {
                'diversification': {'score': diversification, 'max': 25},
                'risk_adjusted_return': {'score': risk_return, 'max': 25},
                'drawdown_resilience': {'score': drawdown, 'max': 25},
                'income_generation': {'score': income, 'max': 25},
            },
        }


class InvestmentInsights:
    """
    Generate actionable investment insights and advice based on portfolio analysis.
    """

    def __init__(self, db_path, ref_date=None):
        self.db_path = db_path
        self.ref_date = ref_date or utils.date2str(datetime.now())

    def generate_insights(self):
        """Analyze portfolio and return a list of actionable insights."""
        insights = []

        # 1. Concentration risk
        try:
            da = DiversificationAnalytics(self.db_path, self.ref_date)
            hhi_data = da.herfindahl_index()
            top5 = da.concentration_top_n(5)

            if hhi_data['hhi'] > 2500:
                insights.append({
                    'category': 'diversification',
                    'severity': 'high',
                    'title': 'High portfolio concentration',
                    'detail': (
                        f"Your portfolio HHI is {hhi_data['hhi']:.0f} "
                        f"({hhi_data['interpretation']}). "
                        f"Top 5 holdings represent {top5['concentration_pct']:.1f}% of value. "
                        f"Consider adding uncorrelated positions to reduce risk."
                    ),
                })
            elif hhi_data['hhi'] > 1500:
                insights.append({
                    'category': 'diversification',
                    'severity': 'medium',
                    'title': 'Moderate concentration',
                    'detail': (
                        f"Your portfolio HHI is {hhi_data['hhi']:.0f}. "
                        f"Consider gradually diversifying into new sectors or geographies."
                    ),
                })

            # Sector concentration
            sector_hhi = da.herfindahl_index('SECTOR')
            if sector_hhi['hhi'] > 3000:
                insights.append({
                    'category': 'diversification',
                    'severity': 'medium',
                    'title': 'Sector concentration risk',
                    'detail': (
                        f"Sector HHI is {sector_hhi['hhi']:.0f}. "
                        f"Heavy sector concentration increases vulnerability to "
                        f"industry-specific downturns."
                    ),
                })

            # Country concentration
            country_hhi = da.herfindahl_index('COUNTRY')
            if country_hhi['hhi'] > 4000:
                insights.append({
                    'category': 'diversification',
                    'severity': 'low',
                    'title': 'Geographic concentration',
                    'detail': (
                        f"Country HHI is {country_hhi['hhi']:.0f}. "
                        f"Consider international diversification to reduce "
                        f"country-specific risk."
                    ),
                })
        except Exception:
            pass

        # 2. Risk metrics insights
        try:
            start = utils.date2str(utils.str2date(self.ref_date) - timedelta(days=365))
            rm = RiskMetrics(self.db_path, start, self.ref_date)
            vol = rm.volatility()
            sharpe = rm.sharpe_ratio()
            dd = rm.max_drawdown()

            if vol is not None and vol > 25:
                insights.append({
                    'category': 'risk',
                    'severity': 'high',
                    'title': 'High portfolio volatility',
                    'detail': (
                        f"Annualized volatility is {vol}%. "
                        f"Consider adding low-correlation assets (bonds, gold) "
                        f"to reduce overall portfolio volatility."
                    ),
                })

            if sharpe is not None and sharpe < 0:
                insights.append({
                    'category': 'risk',
                    'severity': 'high',
                    'title': 'Negative risk-adjusted returns',
                    'detail': (
                        f"Sharpe ratio is {sharpe} (below 0). "
                        f"The portfolio is underperforming a risk-free asset. "
                        f"Review individual positions for persistent losers."
                    ),
                })

            if dd is not None and dd['max_drawdown_pct'] < -30:
                insights.append({
                    'category': 'risk',
                    'severity': 'medium',
                    'title': 'Significant maximum drawdown',
                    'detail': (
                        f"Max drawdown of {dd['max_drawdown_pct']}% "
                        f"(from {dd['peak_date']} to {dd['trough_date']}). "
                        f"Consider implementing stop-loss levels or hedging strategies."
                    ),
                })
        except Exception:
            pass

        # 3. Dividend insights
        try:
            div_analytics = DividendAnalytics(self.db_path)
            yoc = div_analytics.dividend_yield_vs_cost()
            ann_summary = div_analytics.annual_dividend_summary()

            if yoc.get('annualized_yield_on_cost_pct', 0) > 4:
                insights.append({
                    'category': 'income',
                    'severity': 'positive',
                    'title': 'Strong dividend income',
                    'detail': (
                        f"Annualized yield on cost is "
                        f"{yoc['annualized_yield_on_cost_pct']}%. "
                        f"Your portfolio generates solid passive income."
                    ),
                })

            if (ann_summary.get('avg_yoy_growth_pct') is not None
                    and ann_summary['avg_yoy_growth_pct'] > 10):
                insights.append({
                    'category': 'income',
                    'severity': 'positive',
                    'title': 'Growing dividend income',
                    'detail': (
                        f"Average YoY dividend growth is "
                        f"{ann_summary['avg_yoy_growth_pct']}%. "
                        f"Dividend compounding is working in your favor."
                    ),
                })
        except Exception:
            pass

        if not insights:
            insights.append({
                'category': 'general',
                'severity': 'info',
                'title': 'Portfolio looks healthy',
                'detail': 'No significant issues detected. Keep monitoring regularly.',
            })

        return insights
