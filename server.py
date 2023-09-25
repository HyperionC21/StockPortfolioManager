from datetime import datetime, timedelta
from flask import Flask, request
from flask_cors import CORS

import multiprocessing
from backend import fx_fetcher, misc_fetcher, ticker_fetcher, base, api
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

    if filter_kind == 'TICKER':
        ref_portfolio_dt = misc_fetcher_.fetch_fst_trans_on_ticker(filters, 1)['DATE']
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

    ret = api.PortfolioStats(DB_PATH, ref_date).df_portfolio.to_dict()
    
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
        metric_val = api.DivYield(DB_PATH, period_).compute()
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
        metric_val = api.PeriodProfitPerc(DB_PATH, period_).compute()
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

if __name__ == "__main__":
    p = multiprocessing.Process(target=fetch_data)
    p.start()
    app.run(host='0.0.0.0', port=5001, debug=True)
    p.join()