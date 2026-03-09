from datetime import datetime, timedelta
from flask import Flask, request
from flask_cors import CORS

import multiprocessing
from backend import fx_fetcher, misc_fetcher, ticker_fetcher, base, api, benchmarks
from utils import utils

import pandas as pd

app = Flask(__name__)
CORS(app)

DB_PATH = 'core.db'

def fetch_data():
    db_conn = base.BaseDBConnector(DB_PATH)
    ticker_fetcher_ = ticker_fetcher.TickerFetcher(db_conn)
    fx_fetcher_ = fx_fetcher.FxFetcher(db_conn)
    misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)

    ticker_fetcher_.fetch_ticker_hist(misc_fetcher_.fetch_fst_trans(), utils.date2str(datetime.now()))
    fx_fetcher_.fetch_missing_fx(misc_fetcher_.fetch_fst_trans(), utils.date2str(datetime.now()))

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

@app.route("/")
def home():
    return "Hello, World!"

@app.route("/portfolio")
def portfolio():
    ref_date = request.args.get("ref_date", utils.date2str(datetime.now()))

    portfolio_stats_ = api.PortfolioStats(DB_PATH, ref_date)
    return portfolio_stats_.df_portfolio.to_dict()

@app.route("/performance")
def performance():
    
    db_conn = base.BaseDBConnector(DB_PATH)
    misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)
    
    
    start_dt = request.args.get("start_date", misc_fetcher_.fetch_fst_trans())
    end_dt = request.args.get("end_date", utils.date2str(datetime.now()))
    default_interval = request.args.get("default_interval")
    step = int(request.args.get("step", 1))
    kind = request.args.get("kind", 'Absolute')
    filters = request.args.get("filters")
    filter_kind = request.args.get("filter_kind")

    '''
    if filter_kind == 'TICKER':
        ref_portfolio_dt = misc_fetcher_.fetch_fst_trans_on_ticker(filters, 1)['DATE']
    else:
        ref_portfolio_dt = misc_fetcher_.fetch_fst_trans()
    '''

    if filters != 'ALL' and filters is not None and filter_kind is not None:    
        ref_portfolio_dt = misc_fetcher_.fetch_fst_trans_on_filter(filters, filter_kind)
    else:
        ref_portfolio_dt = misc_fetcher_.fetch_fst_trans()

    if default_interval:
        try:
            delta = get_delta_from_interval(default_interval, end_dt)
            start_dt = utils.date2str((utils.str2date(end_dt) - delta))
            
        except Exception as e:
            print(e)
    
    if utils.str2date(ref_portfolio_dt) > utils.str2date(start_dt):
        start_dt = ref_portfolio_dt
    print(start_dt, end_dt)
    date_range = list(utils.daterange(start_dt, end_dt, step))

    df_profits = pd.DataFrame()
    df_profits['date'] = list(date_range)
    ref_profit = api.PortfolioStats(DB_PATH, ref_date=start_dt, filters=filters, filter_kind=filter_kind).get_profit()

    print('start dt: ', start_dt)
    print('ref_portfolio_dt ', ref_portfolio_dt)
    
    if kind == 'Absolute':
        df_profits['profit'] = df_profits.date.apply(lambda x: api.PortfolioStats(DB_PATH, x, filters=filters, filter_kind=filter_kind, ref_profit=ref_profit).get_profit())
    else:
        
        ref_cost = api.PortfolioStats(DB_PATH, filters=filters, filter_kind=filter_kind, ref_date=end_dt).get_cost()

        print('ref cost: ', ref_cost)

        df_profits['profit'] = df_profits.date.apply(lambda x: api.PortfolioStats(DB_PATH, x, filters=filters, filter_kind=filter_kind,
         ref_profit=ref_profit, ref_cost=ref_cost).get_profit_perc())
    df_profits['date'] = df_profits['date'].apply(lambda x: utils.date2str(x))
    
    return df_profits.to_dict()

@app.route("/performance_split")
def performance_split():
    
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

@app.route("/composition")
def composition():
    ref_date = request.args.get("ref_date", utils.date2str(datetime.now()))

    hue = request.args.get('hue', 'TICKER')

    ret = api.PortfolioStats(DB_PATH, ref_date).get_distrib(hue).drop_duplicates().to_dict()
    
    return ret

@app.route("/portfolio_stats")
def portfolio_stats():
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

@app.route("/security_info")
def security_info():
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

@app.route("/new_transaction", methods=['POST'])
def new_transaction():
    data = request.json
    for k in data:
        data[k] = [data[k]]
    df = pd.DataFrame(data)
    print(data)
    print(df)
    db_conn = base.BaseDBConnector(DB_PATH)
    db_conn.insert_data(df, 'TRANSACTION')
    return {}

@app.route("/new_dividend", methods=['POST'])
def new_dividend():
    data = request.json
    for k in data:
        data[k] = [data[k]]
    df = pd.DataFrame(data)
    print(data)
    print(df)
    db_conn = base.BaseDBConnector(DB_PATH)
    db_conn.insert_data(df, 'DIVIDEND')
    return {}

@app.route("/new_quote", methods=['POST'])
def new_quote():
    data = request.json
    for k in data:
        data[k] = [data[k]]
    df = pd.DataFrame(data)
    print(data)
    print(df)
    db_conn = base.BaseDBConnector(DB_PATH)
    db_conn.insert_data(df, 'SECURITY')
    return {}

@app.route("/activity", methods=['GET'])
def activity():
    ticker = request.args.get('ticker', 'AAPL')
    filter_kind = request.args.get('filter_kind', 'TICKER')

    db_conn = base.BaseDBConnector(DB_PATH)
    misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)

    df_activity = misc_fetcher_.fetch_activity(ticker, filter_kind)
    df_activity.columns = list(map(lambda x: x.lower(), df_activity.columns))
    print(df_activity)
    return df_activity.to_dict()



@app.route("/metric", methods=['GET'])
def metric():
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
        metric_val = api.PeriodProfitVal(DB_PATH, period_).compute()
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

    return {
        'metric' : metric_,
        'val' : metric_val
    }

@app.route('/last_trans', methods=['GET'])
def last_trans():
    ticker = request.args.get('ticker', '')
    cnt = request.args.get('cnt', 5)

    db_conn = base.BaseDBConnector(DB_PATH)
    misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)
    res_ = misc_fetcher_.fetch_last_trans_on_ticker(ticker, cnt).to_dict()
    print(res_)
    return res_

@app.route('/last_dividends', methods=['GET'])
def last_dividend():
    ticker = request.args.get('ticker', '')
    cnt = request.args.get('cnt', 5)

    db_conn = base.BaseDBConnector(DB_PATH)
    misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)
    res_ = misc_fetcher_.fetch_last_div_on_ticker(ticker, cnt).to_dict()
    print(res_)
    return res_

## ── Benchmarks & Advanced Metrics Endpoints ──────────────────────────────────

@app.route("/benchmark", methods=['GET'])
def benchmark():
    """Compare portfolio performance against a benchmark index."""
    benchmark_ticker = request.args.get('benchmark', 'SPY')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    step = int(request.args.get('step', 7))
    filters = request.args.get('filters')
    filter_kind = request.args.get('filter_kind')

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
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    step = int(request.args.get('step', 7))
    benchmark_ticker = request.args.get('benchmark', 'SPY')
    risk_free = float(request.args.get('risk_free_rate', benchmarks.DEFAULT_RISK_FREE_RATE))
    filters = request.args.get('filters')
    filter_kind = request.args.get('filter_kind')

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


if __name__ == "__main__":
    p = multiprocessing.Process(target=fetch_data)
    p.start()
    app.run(host='0.0.0.0', port=5001, debug=True)
    p.join()