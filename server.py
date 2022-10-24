from crypt import methods
from datetime import datetime
from flask import Flask, redirect, url_for, request


from backend import fx_fetcher, misc_fetcher, ticker_fetcher, base, api
from utils import utils

import pandas as pd

app = Flask(__name__)

DB_PATH = 'core.db'

db_conn = base.BaseDBConnector(DB_PATH)
ticker_fetcher_ = ticker_fetcher.TickerFetcher(db_conn)
fx_fetcher_ = fx_fetcher.FxFetcher(db_conn)
misc_fetcher_ = misc_fetcher.MiscFetcher(db_conn)

ticker_fetcher_.fetch_ticker_hist(misc_fetcher_.fetch_fst_trans(), utils.date2str(datetime.now()))
fx_fetcher_.fetch_missing_fx(misc_fetcher_.fetch_fst_trans(), utils.date2str(datetime.now()))

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
    step = int(request.args.get("step", 1))
    kind = request.args.get("kind", 'Absolute')


    date_range = utils.daterange(start_dt, end_dt, step)

    df_profits = pd.DataFrame()
    df_profits['date'] = list(date_range)
    if kind == 'Absolute':
        df_profits['profit'] = df_profits.date.apply(lambda x: api.PortfolioStats(DB_PATH, x).get_profit())
    else:
        ref_cost = api.PortfolioStats(DB_PATH, ref_date=end_dt).get_cost()
        df_profits['profit'] = df_profits.date.apply(lambda x: api.PortfolioStats(DB_PATH, x,
         ref_cost=ref_cost).get_profit_perc())
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

    ret = api.PortfolioStats(DB_PATH, ref_date).get_distrib().drop_duplicates().to_dict()

    return ret
    

if __name__ == "__main__":
    app.run(debug=True)