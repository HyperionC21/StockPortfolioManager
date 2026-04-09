import os
import logging
from datetime import datetime, timedelta
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

import multiprocessing
from backend import fx_fetcher, misc_fetcher, ticker_fetcher, base, api, benchmarks
from backend.benchmark_fetcher import BenchmarkFetcher
from utils import utils

import pandas as pd
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

DB_PATH = os.environ.get('DB_PATH', 'core.db')

def fetch_data():
    try:
        db_conn = base.BaseDBConnector(DB_PATH)
        ticker_fetcher_ = ticker_fetcher.TickerFetcher(db_conn)
        fx_fetcher_ = fx_fetcher.FxFetcher(db_conn)
        misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)

        start_dt = misc_fetcher_.fetch_fst_trans()
        end_dt = utils.date2str(datetime.now())
        ticker_fetcher_.fetch_ticker_hist(start_dt, end_dt)
        fx_fetcher_.fetch_missing_fx(start_dt, end_dt)
        BenchmarkFetcher(db_conn).fetch_missing(start_dt, end_dt)
        logger.info("Background data fetch completed successfully")
    except Exception as e:
        logger.error(f"Background data fetch failed: {e}")

# Auto-start background data fetch (works with both gunicorn and direct run)
_fetch_started = False
def _start_fetch_once():
    global _fetch_started
    if not _fetch_started:
        _fetch_started = True
        t = threading.Thread(target=fetch_data, daemon=True)
        t.start()
        logger.info("Started background data fetch thread")

_start_fetch_once()

TIME_INTERVALS = ['1W', '1M', '1Q', '6M', '1Y', 'YTD', '3Y', '5Y']

def get_delta_from_interval(default_interval, ref_dt=None):
    if default_interval == '1W':
        return timedelta(days=7)
    elif default_interval == '1M':
        return timedelta(days=30)
    elif default_interval == '1Q':
        return timedelta(days=90)
    elif default_interval == '6M':
        return timedelta(days=180)
    elif default_interval == '1Y':
        return timedelta(days=365)
    elif default_interval == '3Y':
        return timedelta(3 * 365)
    elif default_interval == '5Y':
        return timedelta(5 * 365)
    elif default_interval == 'YTD':
        ref_dt = utils.str2date(ref_dt)
        start_dt = ref_dt.replace(month=1, day=1)
        return ref_dt - start_dt
    raise Exception(f'Interval {default_interval} not registered for parsing')


# --- Health check ---
@app.route("/health")
def health():
    try:
        db_conn = base.BaseDBConnector(DB_PATH)
        db_conn.read_query("SELECT 1")
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


# --- Dashboard summary (single call for key metrics) ---
@app.route("/dashboard")
def dashboard():
    try:
        ref_date = datetime.now()
        stats = api.PortfolioStats(DB_PATH, ref_date)

        nav = float(np.round(stats.get_nav(), 2))
        cost = float(np.round(stats.get_cost(), 2))
        profit = float(np.round(stats.get_profit(), 2))
        fee = float(np.round(stats.get_fee(), 2))
        profit_perc = float(np.round(profit * 100 / (cost + 1e-24), 2))
        n_holdings = int(len(stats.df_portfolio[stats.df_portfolio.N_SHARES > 0]))

        # Top gainers and losers
        active = stats.df_portfolio[stats.df_portfolio.N_SHARES > 0].copy()
        active = active.sort_values('PROFIT%', ascending=False)
        top_gainers = active.head(3)[['TICKER', 'PROFIT%']].to_dict(orient='records')
        top_losers = active.tail(3)[['TICKER', 'PROFIT%']].to_dict(orient='records')

        return jsonify({
            "nav": nav,
            "cost": cost,
            "profit": profit,
            "profit_perc": profit_perc,
            "total_fee": fee,
            "n_holdings": n_holdings,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "as_of": utils.date2str(ref_date),
        })
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return jsonify({"service": "StockPortfolioManager API", "status": "running"})

@app.route("/portfolio")
def portfolio():
    try:
        ref_date = request.args.get("ref_date", utils.date2str(datetime.now()))
        portfolio_stats_ = api.PortfolioStats(DB_PATH, ref_date)
        return portfolio_stats_.df_portfolio.to_dict()
    except Exception as e:
        logger.error(f"Portfolio error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/performance")
def performance():
    try:
        db_conn = base.BaseDBConnector(DB_PATH)
        misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)

        start_dt = request.args.get("start_date", misc_fetcher_.fetch_fst_trans())
        end_dt = request.args.get("end_date", utils.date2str(datetime.now()))
        default_interval = request.args.get("default_interval")
        step = int(request.args.get("step", 1))
        kind = request.args.get("kind", 'Absolute')
        filters = request.args.get("filters")
        filter_kind = request.args.get("filter_kind")

        if filters != 'ALL' and filters is not None and filter_kind is not None:
            ref_portfolio_dt = misc_fetcher_.fetch_fst_trans_on_filter(filters, filter_kind)
        else:
            ref_portfolio_dt = misc_fetcher_.fetch_fst_trans()

        if default_interval:
            try:
                delta = get_delta_from_interval(default_interval, end_dt)
                start_dt = utils.date2str((utils.str2date(end_dt) - delta))
            except Exception as e:
                logger.warning(f"Interval parse error: {e}")

        if utils.str2date(ref_portfolio_dt) > utils.str2date(start_dt):
            start_dt = ref_portfolio_dt

        date_range = list(utils.daterange(start_dt, end_dt, step))

        df_profits = pd.DataFrame()
        df_profits['date'] = list(date_range)
        ref_profit = api.PortfolioStats(DB_PATH, ref_date=start_dt, filters=filters, filter_kind=filter_kind).get_profit()

        if kind == 'Absolute':
            df_profits['profit'] = df_profits.date.apply(lambda x: api.PortfolioStats(DB_PATH, x, filters=filters, filter_kind=filter_kind, ref_profit=ref_profit).get_profit())
        else:
            ref_cost = api.PortfolioStats(DB_PATH, filters=filters, filter_kind=filter_kind, ref_date=end_dt).get_cost()
            df_profits['profit'] = df_profits.date.apply(lambda x: api.PortfolioStats(DB_PATH, x, filters=filters, filter_kind=filter_kind,
             ref_profit=ref_profit, ref_cost=ref_cost).get_profit_perc())
        df_profits['date'] = df_profits['date'].apply(lambda x: utils.date2str(x))

        return df_profits.to_dict()
    except Exception as e:
        logger.error(f"Performance error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/performance_split")
def performance_split():
    try:
        db_conn = base.BaseDBConnector(DB_PATH)
        misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)
        start_dt = request.args.get("start_date", misc_fetcher_.fetch_fst_trans())
        end_dt = request.args.get("end_date", utils.date2str(datetime.now()))
        step = int(request.args.get("step", 1))

        dfs = []
        date_range = utils.daterange(start_dt, end_dt, step)
        for date_ in date_range:
            portfolio_img = api.PortfolioStats(DB_PATH, date_)
            profit_perc = portfolio_img.get_profit_perc_distrib()
            profit_perc['DATE'] = [utils.date2str(date_)] * len(profit_perc)
            dfs.append(profit_perc)

        df_res = pd.concat(dfs, axis=0)
        ret = df_res.to_dict(orient='list')
        return ret
    except Exception as e:
        logger.error(f"Performance split error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/composition")
def composition():
    try:
        ref_date = request.args.get("ref_date", utils.date2str(datetime.now()))
        hue = request.args.get('hue', 'TICKER')
        ret = api.PortfolioStats(DB_PATH, ref_date).get_distrib(hue).drop_duplicates().to_dict()
        return ret
    except Exception as e:
        logger.error(f"Composition error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/portfolio_stats")
def portfolio_stats():
    try:
        ref_date = datetime.now()
        stats = api.PortfolioStats(DB_PATH, ref_date)
        stats.df_portfolio['PRICE'] = stats.df_portfolio['PRICE'].round(2)
        stats.df_portfolio['PROFIT'] = stats.df_portfolio['PROFIT'].astype(int)
        stats.df_portfolio['PROFIT%'] = stats.df_portfolio['PROFIT%'].round(2)
        stats.df_portfolio['TOTAL_FEE'] = stats.df_portfolio['TOTAL_FEE'].astype(int)
        stats.df_portfolio['TOTAL_VALUE'] = stats.df_portfolio['TOTAL_VALUE'].astype(int)
        stats.df_portfolio['TOTAL_COST'] = stats.df_portfolio['TOTAL_COST'].astype(int)
        stats.df_portfolio['PORTFOLIO%'] = stats.df_portfolio['PORTFOLIO%'].round(2)
        stats.df_portfolio = stats.df_portfolio[stats.df_portfolio.N_SHARES > 0]
        ret = stats.df_portfolio.to_dict()
        return ret
    except Exception as e:
        logger.error(f"Portfolio stats error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/security_info")
def security_info():
    try:
        security = request.args.get('security')
        hue = request.args.get('hue', 'TICKER')
        ref_date = request.args.get('dt', utils.date2str(datetime.now()))

        ret = {}
        if security:
            stats = api.PortfolioStats(DB_PATH, ref_date)
            security_stats = stats.get_security_info(security, hue)
            if len(security_stats) > 0:
                ret = security_stats[0]
        return ret
    except Exception as e:
        logger.error(f"Security info error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/new_transaction", methods=['POST'])
def new_transaction():
    try:
        data = request.json
        if not data or 'ticker' not in data:
            return jsonify({"error": "Missing required field: ticker"}), 400
        for k in data:
            data[k] = [data[k]]
        df = pd.DataFrame(data)
        db_conn = base.BaseDBConnector(DB_PATH)
        db_conn.insert_data(df, 'TRANSACTION')
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"New transaction error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/new_dividend", methods=['POST'])
def new_dividend():
    try:
        data = request.json
        if not data or 'ticker' not in data:
            return jsonify({"error": "Missing required field: ticker"}), 400
        for k in data:
            data[k] = [data[k]]
        df = pd.DataFrame(data)
        db_conn = base.BaseDBConnector(DB_PATH)
        db_conn.insert_data(df, 'DIVIDEND')
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"New dividend error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/new_quote", methods=['POST'])
def new_quote():
    try:
        data = request.json
        for k in data:
            data[k] = [data[k]]
        df = pd.DataFrame(data)
        db_conn = base.BaseDBConnector(DB_PATH)
        db_conn.insert_data(df, 'SECURITY')
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.error(f"New quote error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/activity", methods=['GET'])
def activity():
    try:
        ticker = request.args.get('ticker', 'AAPL')
        filter_kind = request.args.get('filter_kind', 'TICKER')

        db_conn = base.BaseDBConnector(DB_PATH)
        misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)

        df_activity = misc_fetcher_.fetch_activity(ticker, filter_kind)
        df_activity.columns = list(map(lambda x: x.lower(), df_activity.columns))
        return df_activity.to_dict()
    except Exception as e:
        logger.error(f"Activity error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/metric", methods=['GET'])
def metric():
    try:
        metric_ = request.args.get('metric')
        period_ = request.args.get('period', 'ALL')
        ticker = request.args.get('ticker')
        filter_kind = request.args.get('filter_kind')
        ref_dt = request.args.get('ref_dt', utils.date2str(datetime.now()))

        if ticker == 'ALL':
            ticker = None
            filter_kind = None
        metric_val = 'N/A'

        if metric_ == 'div_yield':
            metric_val = api.DivYield(DB_PATH, period_, ticker, filter_kind).compute()
        elif metric_ == 'div_val':
            metric_val = api.DivVal(DB_PATH, period_, ticker, filter_kind).compute()
        elif metric_ == 'nav':
            metric_val = api.Nav(DB_PATH, period_, ticker, filter_kind).compute()
        elif metric_ == 'cost_basis':
            metric_val = api.CostBasis(DB_PATH, period_, ticker, filter_kind).compute()
        elif metric_ == 'profit':
            metric_val = api.Profit(DB_PATH, period_).compute()
        elif metric_ == 'fee':
            metric_val = api.Fee(DB_PATH, period_).compute()
        elif metric_ == 'annualized_profit_period':
            metric_val = api.PeriodProfitVal(DB_PATH, period_, ticker, filter_kind).compute()
        elif metric_ == 'annualized_profit_perc_period':
            metric_val = api.PeriodProfitPerc(DB_PATH, period_, ticker, filter_kind).compute()
        elif metric_ == 'PE':
            metric_val = api.PE(ticker, DB_PATH).compute()
        elif metric_ == 'security_div_amt':
            metric_val = api.DivSecurity(ticker, DB_PATH).compute()
        elif metric_ == 'security_cost_basis_amt':
            metric_val = api.CostBasisSecurity(ticker, DB_PATH).compute()
        elif metric_ == 'security_equity_gain_amt':
            metric_val = api.EquityGainSecurity(ticker, ref_dt, DB_PATH).compute()
        elif metric_ == 'security_equity_amt':
            metric_val = api.EquityAmtSecurity(ticker, ref_dt, DB_PATH).compute()

        # Convert numpy types to native Python for JSON serialization
        if hasattr(metric_val, 'item'):
            metric_val = metric_val.item()

        return jsonify({
            'metric': metric_,
            'val': metric_val
        })
    except Exception as e:
        logger.error(f"Metric error ({metric_}): {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/last_trans', methods=['GET'])
def last_trans():
    try:
        ticker = request.args.get('ticker', '')
        cnt = request.args.get('cnt', 5)

        db_conn = base.BaseDBConnector(DB_PATH)
        misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)
        res_ = misc_fetcher_.fetch_last_trans_on_ticker(ticker, cnt).to_dict()
        return res_
    except Exception as e:
        logger.error(f"Last trans error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/last_dividends', methods=['GET'])
def last_dividend():
    try:
        ticker = request.args.get('ticker', '')
        cnt = request.args.get('cnt', 5)

        db_conn = base.BaseDBConnector(DB_PATH)
        misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)
        res_ = misc_fetcher_.fetch_last_div_on_ticker(ticker, cnt).to_dict()
        return res_
    except Exception as e:
        logger.error(f"Last dividends error: {e}")
        return jsonify({"error": str(e)}), 500

## ── Benchmarks & Advanced Metrics Endpoints ──────────────────────────────────

@app.route("/benchmark", methods=['GET'])
def benchmark():
    """Compare portfolio performance against a benchmark index."""
    benchmark_ticker = request.args.get('benchmark', 'SPY')
    end_date = request.args.get('end_date', utils.date2str(datetime.now()))
    start_date = request.args.get('start_date')
    step = int(request.args.get('step', 7))
    filters = request.args.get('filters')
    filter_kind = request.args.get('filter_kind')
    default_interval = request.args.get('default_interval')

    if default_interval:
        try:
            delta = get_delta_from_interval(default_interval, end_date)
            start_date = utils.date2str(utils.str2date(end_date) - delta)
        except Exception:
            pass

    pb = benchmarks.PortfolioBenchmark(
        DB_PATH, start_date, end_date, step, filters, filter_kind
    )
    return pb.compare_performance(benchmark_ticker)


@app.route("/benchmark_multi", methods=['GET'])
def benchmark_multi():
    """Compare portfolio against multiple benchmarks."""
    bench_list = request.args.get('benchmarks', 'SPY,QQQ,AGG')
    bench_tickers = [b.strip() for b in bench_list.split(',')]
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    step = int(request.args.get('step', 7))

    pb = benchmarks.PortfolioBenchmark(DB_PATH, start_date, end_date, step)
    return {'comparisons': pb.multi_benchmark_comparison(bench_tickers)}


@app.route("/risk_metrics", methods=['GET'])
def risk_metrics():
    """Compute all risk metrics (Sharpe, Sortino, Vol, Drawdown, Beta, Alpha)."""
    end_date = request.args.get('end_date', utils.date2str(datetime.now()))
    start_date = request.args.get('start_date')
    step = int(request.args.get('step', 7))
    benchmark_ticker = request.args.get('benchmark', 'SPY')
    risk_free = float(request.args.get('risk_free_rate', benchmarks.DEFAULT_RISK_FREE_RATE))
    filters = request.args.get('filters')
    filter_kind = request.args.get('filter_kind')
    default_interval = request.args.get('default_interval')

    if default_interval:
        try:
            delta = get_delta_from_interval(default_interval, end_date)
            start_date = utils.date2str(utils.str2date(end_date) - delta)
        except Exception:
            pass

    rm = benchmarks.RiskMetrics(
        DB_PATH, start_date, end_date, step, risk_free, filters, filter_kind
    )
    return rm.compute_all(benchmark_ticker)


@app.route("/diversification", methods=['GET'])
def diversification():
    """Portfolio diversification analysis (HHI, concentration)."""
    ref_date = request.args.get('ref_date', utils.date2str(datetime.now()))
    hue = request.args.get('hue', 'TICKER')
    filters = request.args.get('filters')
    filter_kind = request.args.get('filter_kind')

    da = benchmarks.DiversificationAnalytics(DB_PATH, ref_date, filters, filter_kind)

    return {
        'herfindahl': da.herfindahl_index(hue),
        'top_5_concentration': da.concentration_top_n(5, hue),
        'all_dimensions': da.diversification_by_dimension(),
    }


@app.route("/correlation", methods=['GET'])
def correlation():
    """Pairwise ticker correlation matrix."""
    ref_date = request.args.get('ref_date', utils.date2str(datetime.now()))
    period_days = int(request.args.get('period_days', 365))
    step = int(request.args.get('step', 7))

    da = benchmarks.DiversificationAnalytics(DB_PATH, ref_date)
    return da.correlation_matrix(period_days, step)


@app.route("/dividends_analysis", methods=['GET'])
def dividends_analysis():
    """Comprehensive dividend analytics."""
    div_analytics = benchmarks.DividendAnalytics(DB_PATH)
    return {
        'annual_summary': div_analytics.annual_dividend_summary(),
        'by_ticker': div_analytics.dividend_by_ticker(),
        'yield_on_cost': div_analytics.dividend_yield_vs_cost(),
    }


@app.route("/rebalance", methods=['GET'])
def rebalance():
    """Get rebalancing suggestions (equal weight)."""
    ref_date = request.args.get('ref_date', utils.date2str(datetime.now()))
    hue = request.args.get('hue', 'TICKER')
    tolerance = float(request.args.get('tolerance', 2.0))

    rb = benchmarks.RebalancingSuggestions(DB_PATH, ref_date)
    return rb.equal_weight_rebalance(hue, tolerance)


@app.route("/rebalance_custom", methods=['POST'])
def rebalance_custom():
    """Get rebalancing suggestions for custom target allocations."""
    data = request.json
    targets = data.get('targets', {})
    hue = data.get('hue', 'TICKER')
    tolerance = float(data.get('tolerance', 2.0))
    ref_date = data.get('ref_date', utils.date2str(datetime.now()))

    rb = benchmarks.RebalancingSuggestions(DB_PATH, ref_date)
    return rb.custom_target_rebalance(targets, hue, tolerance)


@app.route("/health_score", methods=['GET'])
def health_score():
    """Portfolio health score (0-100) with grade and breakdown."""
    ref_date = request.args.get('ref_date', utils.date2str(datetime.now()))
    period = request.args.get('period', '1Y')

    hs = benchmarks.PortfolioHealthScore(DB_PATH, period, ref_date)
    return hs.compute()


@app.route("/insights", methods=['GET'])
def insights():
    """Actionable investment insights and advice."""
    ref_date = request.args.get('ref_date', utils.date2str(datetime.now()))
    ii = benchmarks.InvestmentInsights(DB_PATH, ref_date)
    return {'insights': ii.generate_insights()}


@app.route("/available_benchmarks", methods=['GET'])
def available_benchmarks():
    """List available benchmark indices for comparison."""
    return {'benchmarks': [{'ticker': k, 'name': v} for k, v in benchmarks.BENCHMARKS.items()]}


@app.route("/bet_tracking", methods=['GET'])
def bet_tracking():
    """BET index top-10 vs user's Romanian holdings — weights and divergence."""
    try:
        ref_date = request.args.get('ref_date', utils.date2str(datetime.now()))
        tracker = benchmarks.BETTracker(DB_PATH)
        return jsonify(tracker.get_tracking(ref_date))
    except Exception as e:
        logger.error(f"BET tracking error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    debug_mode = os.getenv('FLASK_ENV', 'production') == 'development'
    p = multiprocessing.Process(target=fetch_data)
    p.start()
    app.run(host='0.0.0.0', port=5001, debug=True)
    p.join()
