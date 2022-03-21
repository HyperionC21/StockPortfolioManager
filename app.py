import requests
from flask import Flask
from flask import request, render_template
from utils import utils

import pandas as pd
import numpy as np
import json

import yfinance as yf
from datetime import datetime, timedelta
from backend import base, reporting
from utils import utils
import plotly.express as px

app = Flask(__name__)


@app.route('/', methods = ['GET', 'POST'])
def home_page():
    return render_template(r'home_page.html')

@app.route('/roi', methods = ['GET', 'POST'])
def roi_display():
    return render_template(r'roi.html')

@app.route('/composition', methods = ['GET', 'POST'])
def composition_display():
    return render_template(r'composition.html')

@app.route('/profit', methods = ['GET', 'POST'])
def profit_display():
    return render_template(r'profit.html')

@app.route('/table', methods = ['GET', 'POST'])
def table_diplay():
    return render_template(r'table.html')

@app.route('/security', methods = ['GET', 'POST'])
def security_form_handler():

    values = request.args.to_dict(flat=True)
    for k in values.keys():
        values[k] = [values[k]]
    
    db_connector = base.BaseDBConnector('core.db')
    security_handler = base.TableHandler(db_connector, 'SECURITY', 'TICKER')

    try:
        security_handler.insert_val(values)
    except Exception as e:
        print(e)


    return render_template(r'security_form.html')


@app.route('/dividend', methods = ['GET', 'POST'])
def dividend_form_handler():

    values = request.args.to_dict(flat=True)
    for k in values.keys():
        values[k] = [values[k]]

    values['ID'] = None

    db_connector = base.BaseDBConnector('core.db')
    dividend_handler = base.TableHandler(db_connector, 'DIVIDEND', '')

    try:
        dividend_handler.insert_val(values)
    except Exception as e:
        print(e)


    return render_template(r'dividend_form.html')

@app.route('/transaction', methods = ['GET', 'POST'])
def transaction_form_handler():

    values = request.args.to_dict(flat=True)
    for k in values.keys():
        values[k] = [values[k]]
    
    values['ID'] = None

    db_connector = base.BaseDBConnector('core.db')
    transaction_handler = base.TableHandler(db_connector, 'TRANSACTION', 'ID')

    try:
        transaction_handler.insert_val(values)
    except Exception as e:
        print(e)


    return render_template(r'transaction_form.html')


if __name__ == "__main__":

    START_DT = '2022-01-10'
    now_ = utils.date2str(datetime.now())

    db_connector = base.BaseDBConnector('core.db')
    data_fetcher = base.DataFetcher(db_connector)
    reporter = reporting.Reporter(data_fetcher)

    missing_data_getter = base.DBUpdater(db_conn=db_connector)
    _ = missing_data_getter.fetch_missing_fx(START_DT, now_)
    _ = missing_data_getter.fetch_missing_securities_yf(START_DT, now_)
    _ = missing_data_getter.fetch_missing_securities_bvb(START_DT, now_)

    ref_cost = reporter.get_portfolio_info(1, now_)['cost']

    df_composition = reporter.get_portfolio_info(1, now_, ref_cost=ref_cost)['df']
    df_composition['PROFIT'] = np.round(df_composition['VALUE'] - df_composition['TOTAL_COST'], 2)
    df_composition['PROFIT%'] = np.round(df_composition['PROFIT'] * 100 / df_composition['TOTAL_COST'], 2)


    df_composition['TOTAL_COST'] = df_composition['TOTAL_COST'].astype(int)
    df_composition['AVG_COST'] = np.round(df_composition['TOTAL_COST'] / df_composition['N_SHARES'], 2)
    df_composition['PRICE'] = df_composition['PRICE'].apply(lambda x: np.round(x, 2))
    df_composition['LCY_PRICE'] = np.round(df_composition['PRICE'] * df_composition['FX'], 2)
    df_composition['VALUE'] = df_composition['VALUE'].astype(int)
    df_composition['PROFIT'] = df_composition['PROFIT'].astype(int)

    df_composition.to_html('templates/table.html', justify='center', index=False)
    # WRITE ROI HTML
    df_evolution = pd.DataFrame()
    df_evolution['DT'] = list(utils.daterange(START_DT, now_))
    df_evolution['RETURN'] = df_evolution['DT'].apply(lambda x: reporter.get_portfolio_info(1, x, ref_cost=ref_cost)['profit_perc'])
    df_evolution['RETURN'] = df_evolution['RETURN'].apply(lambda x: np.round(x, 2))

    fig_roi = px.line(df_evolution, x='DT', y=['RETURN'], title='Portfolio ROI')
    fig_roi.write_html('templates/roi.html')
    
    # WRITE COMPOSITION HTML
    fig_value_pie = px.pie(df_composition, names='TICKER', values='VALUE', title = 'Value distribution', width=500)
    fig_value_pie.write_html('templates/composition.html')
    

    # WRITE PROFIT HTML

    profit_perc = px.bar(df_composition, x='TICKER', y='PROFIT%', color='TICKER', title='Percentage profit')
    profit_perc.write_html('templates/profit.html')
    app.run(debug=True)
    
