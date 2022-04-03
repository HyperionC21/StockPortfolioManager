# backend
import pandas as pd
import numpy as np
import json

from backend import base, reporting
from utils import utils
from datetime import datetime


# frontend
from dash import Dash, html, dcc
from dash import dash_table
import plotly.express as px
app = Dash(__name__)

def get_evolution(start_dt, end_dt):
    df_evolution = pd.DataFrame()
    df_evolution['DT'] = list(utils.daterange(start_dt, end_dt))
    df_evolution['RETURN'] = df_evolution['DT'].apply(lambda x: reporter.get_portfolio_info(1, x, ref_cost=ref_cost)['profit_perc'])
    df_evolution['RETURN'] = df_evolution['RETURN'].apply(lambda x: np.round(x, 2))

    return df_evolution

def get_composition(ref_date, ref_cost):
    df_composition = reporter.get_portfolio_info(1, ref_date, ref_cost=ref_cost)['df']
    df_composition['PROFIT'] = np.round(df_composition['VALUE'] - df_composition['TOTAL_COST'], 2)
    df_composition['PROFIT%'] = np.round(df_composition['PROFIT'] * 100 / df_composition['TOTAL_COST'], 2)

    df_composition['FX'] = np.round(df_composition['FX'], 2)

    df_composition['TOTAL_COST'] = df_composition['TOTAL_COST'].astype(int)
    df_composition['PRICE'] = df_composition['PRICE'].apply(lambda x: np.round(x, 2))
    df_composition['VALUE'] = df_composition['VALUE'].astype(int)
    df_composition['PROFIT'] = df_composition['PROFIT'].astype(int)

    df_composition = df_composition.sort_values(by='VALUE', ascending=False)
    return df_composition

if __name__ == '__main__':
    
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

    data = reporter.get_portfolio_info(1, now_, ref_cost=ref_cost)

    df = data['df']

    df_ev = get_evolution(START_DT, now_)

    fig_roi = px.line(df_ev, x='DT', y=['RETURN'])

    df_comp = get_composition(now_, ref_cost)

    fig_value_pie = px.pie(df_comp, names='TICKER', values='VALUE', title='Portfolio value')
    fig_cost_pie = px.pie(df_comp, names='TICKER', values='TOTAL_COST', title='Portfolio invested')

    fig_profit_perc = px.bar(df_comp, x='TICKER', y='PROFIT%', color='TICKER', title='Percentage profit')
    fig_profit = px.bar(df_comp, x='TICKER', y='PROFIT', color='TICKER', title='Absolute profit')
    
    roi_div = html.Div(
        children=[
            dcc.Graph(figure=fig_roi),
            html.Div([
                dcc.Graph(figure=fig_value_pie),
                dcc.Graph(figure=fig_cost_pie)
                ], style={'display': 'flex', 'flex-direction': 'row'}
            ),
            dcc.Graph(figure=fig_profit_perc),
            dcc.Graph(figure=fig_profit)
        ],
        style={'display': 'flex', 'flex-direction': 'column', 'width' : '1000'}
    )

    app.layout = roi_div




    app.run_server()