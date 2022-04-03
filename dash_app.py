# backend
import pandas as pd
import numpy as np
import json

from backend import base, reporting
from utils import utils
from datetime import datetime
import flask


# frontend
from dash import Dash, html, dcc, Input, Output, callback
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

def get_form(fields, id_):
    def get_field(name):
        return html.Div([
                    html.Label(name),
                    dcc.Input(name=name),
                ],
                style={'display': 'flex', 'flex-direction': 'row', 'width' : '1000'}
            )

    fields = list(map(lambda x: get_field(x), fields))

    form_security = html.Form([
        *fields,
        html.Button('Submit', type='submit')
    ], action=f'/post_{id_}', method='post', id=id_)

    return form_security

INPUT_FORM_FIELDS = {
    'security' : ['TICKER', 'SECTOR', 'COUNTRY', 'FX', 'MARKET', 'SRC'],
    'transaction' : ['TICKER', 'PRICE', 'FX', 'AMOUNT', 'DATE'],
    'security_values' : ['TICKER', 'DATE', 'CLOSE']
}

gl_form_name = 'security'

if __name__ == '__main__':
    
    START_DT = '2022-01-10'
    now_ = utils.date2str(datetime.now())

    
    db_connector = base.BaseDBConnector('core.db')
    data_fetcher = base.DataFetcher(db_connector)
    reporter = reporting.Reporter(data_fetcher)

    # table handlers
    
    
    

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
        id='page-1-content',
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

    index_page = html.Div([
        dcc.Link('Go to statistics', href='/page-1'),
        html.Br(),
        dcc.Link('Go to security', href='/security_id'),
        html.Br(),
        dcc.Link('Go to transactions', href='/transaction_id'),
        html.Br(),
        dcc.Link('Go to security values', href='/security_values_id'),
    ])

    page_1_layout = html.Div([
        roi_div,
        dcc.Link('Go back to home', href='/'),
    ])

    security_form = html.Div([
        get_form(INPUT_FORM_FIELDS['security'], 'security_id'),
        dcc.Link('Go back to home', href='/')
    ])

    transaction_form = html.Div([
        get_form(INPUT_FORM_FIELDS['transaction'], 'transaction_id'),
        dcc.Link('Go back to home', href='/')
    ])

    security_values_form = html.Div([
        get_form(INPUT_FORM_FIELDS['security_values'], 'security_values_id'),
        dcc.Link('Go back to home', href='/')
    ])

    @callback(Output('page-content', 'children'),
              [Input('url', 'pathname')])
    def display_page(pathname):
        if pathname == '/page-1':
            return page_1_layout
        elif pathname == '/security_id':
            return security_form
        elif pathname == '/transaction_id':
            return transaction_form
        elif pathname == '/security_values_id':
            return security_values_form
        else:
            return index_page
    
    @app.server.route('/post_security_id', methods=['POST'])
    def on_security_post():

        db_connector = base.BaseDBConnector('core.db')
        security_t_handler = base.TableHandler(db_connector, 'SECURITY', '')

        data = dict(flask.request.form)

        for k in data.keys():
            data[k] = [data[k]]

        security_t_handler.insert_val(data)
        return flask.redirect('/')

    @app.server.route('/post_transaction_id', methods=['POST'])
    def on_transaction_post():

        db_connector = base.BaseDBConnector('core.db')
        transaction_t_handler = base.TableHandler(db_connector, 'TRANSACTION', '')
        data = dict(flask.request.form)

        for k in data.keys():
            data[k] = [data[k]]
        
        transaction_t_handler.insert_val(data)
        return flask.redirect('/')

    @app.server.route('/post_security_values_id', methods=['POST'])
    def on_security_values_post():
        
        db_connector = base.BaseDBConnector('core.db')
        security_values_t_handler = base.TableHandler(db_connector, 'SECURITY_VALUES', '')
        
        data = dict(flask.request.form)
        
        for k in data.keys():
            data[k] = [data[k]]

        security_values_t_handler.insert_val(data)
        return flask.redirect('/')

    app.layout = html.Div([
        dcc.Location(id='url', refresh=False),
        html.Div(id='page-content')
    ])

    app.run_server()