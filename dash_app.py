# backend
from distutils.log import debug
import statistics
from turtle import width
import pandas as pd
import numpy as np
import json
import argparse

from backend import base, reporting
from utils import utils
from datetime import datetime
import flask


from dash_ui.figures import *
from dash_ui.components import *


# frontend
from dash import Dash, html, dcc, Input, Output, callback
from dash import dash_table
import dash
import plotly.express as px
app = Dash(__name__)

# CREATE INPUT PARSER
parser = argparse.ArgumentParser()
parser.add_argument("--db-path", type=str, help="Path for DB", default='core.db')

args = parser.parse_args()



def update_data(db_path):

    db_connector = base.BaseDBConnector(db_path)
    missing_data_getter = base.DBUpdater(db_conn=db_connector)
    _ = missing_data_getter.fetch_missing_fx(START_DT, now_)
    _ = missing_data_getter.fetch_missing_securities_yf(START_DT, now_)
    _ = missing_data_getter.fetch_missing_securities_bvb(START_DT, now_)


START_DT = '2022-01-10'
now_ = utils.date2str(datetime.now())


if __name__ == '__main__':
    # UPDATE BACKED
    update_data(args.db_path)

    # GET DISPLAY FIGURES
    vis_data = get_visual_data(START_DT, now_, args.db_path)

    index_page = get_index_page()
    statistics_page = get_statistics_page(vis_data=vis_data, start_dt=START_DT, end_dt=now_, db_path=args.db_path)

    # CREATE INPUT FORMS
    security_form = get_security_form(args.db_path)
    security_values_form = get_security_values_form(args.db_path)
    transaction_form = get_transaction_form(args.db_path)

    @callback(Output('page-content', 'children'),
              [Input('url', 'pathname')])
    def display_page(pathname):
        if pathname == '/statistics':
            return statistics_page
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
        global args
        db_connector = base.BaseDBConnector(args.db_path)
        security_t_handler = base.TableHandler(db_connector, 'SECURITY', '')

        data = dict(flask.request.form)

        for k in data.keys():
            data[k] = [data[k]]

        security_t_handler.insert_val(data)
        return flask.redirect('/')

    @app.server.route('/post_transaction_id', methods=['POST'])
    def on_transaction_post():
        global args

        db_connector = base.BaseDBConnector(args.db_path)
        transaction_t_handler = base.TableHandler(db_connector, 'TRANSACTION', '')
        data = dict(flask.request.form)

        for k in data.keys():
            data[k] = [data[k]]
        
        transaction_t_handler.insert_val(data)
        return flask.redirect('/')

    @app.server.route('/post_security_values_id', methods=['POST'])
    def on_security_values_post():
        global args

        db_connector = base.BaseDBConnector(args.db_path)
        security_values_t_handler = base.TableHandler(db_connector, 'SECURITY_VALUES', '')
        
        data = dict(flask.request.form)
        
        for k in data.keys():
            data[k] = [data[k]]

        security_values_t_handler.insert_val(data)
        return flask.redirect('/')

    @app.callback(
        Output('roi_graph_id', 'figure'),
        Input('roi_range', 'start_date'),
        Input('roi_range', 'end_date'),
        Input('period_dropdown_id', 'value'))
    def update_output_roi(start_date, end_date, value):
        ctx = dash.callback_context
        if ctx.triggered[0]['prop_id'] == 'period_dropdown_id.value':
            end_dt = utils.str2date(now_)
            
            from datetime import timedelta

            start_dt = utils.str2date(START_DT)
            
            if value == 'MTD':
                start_dt = end_dt.replace(day=1)
            elif value == 'WTD':
                start_dt = end_dt - timedelta(days=end_dt.weekday())
            elif value == 'YTD':
                start_dt = end_dt.replace(month=1, day=1) 
            
            if start_dt < utils.str2date(START_DT):
                start_dt = utils.str2date(START_DT)

            start_dt = utils.date2str(start_dt)
            end_dt = utils.date2str(end_dt)

            return get_visual_data(start_dt, end_dt, args.db_path)['fig_roi']
        else:
            return get_visual_data(start_date, end_date, args.db_path)['fig_roi']

    @app.callback(
        Output('profit_graph_id', 'figure'),
        Input('roi_range', 'start_date'),
        Input('roi_range', 'end_date'),
        Input('period_dropdown_id', 'value'))
    def update_output_profit(start_date, end_date, value):
        ctx = dash.callback_context
        if ctx.triggered[0]['prop_id'] == 'period_dropdown_id.value':
            end_dt = utils.str2date(now_)
            
            from datetime import timedelta

            start_dt = utils.str2date(START_DT)
            
            if value == 'MTD':
                start_dt = end_dt.replace(day=1)
            elif value == 'WTD':
                start_dt = end_dt - timedelta(days=end_dt.weekday())
            elif value == 'YTD':
                start_dt = end_dt.replace(month=1, day=1) 
            
            if start_dt < utils.str2date(START_DT):
                start_dt = utils.str2date(START_DT)

            start_dt = utils.date2str(start_dt)
            end_dt = utils.date2str(end_dt)

            return get_visual_data(start_dt, end_dt, args.db_path)['graph_profit']
        else:
            return get_visual_data(start_date, end_date, args.db_path)['graph_profit']

    @app.callback(
        Output('nav_graph_id', 'figure'),
        Input('roi_range', 'start_date'),
        Input('roi_range', 'end_date'),
        Input('period_dropdown_id', 'value'))
    def update_output_nav(start_date, end_date, value):
        ctx = dash.callback_context
        if ctx.triggered[0]['prop_id'] == 'period_dropdown_id.value':
            end_dt = utils.str2date(now_)
            
            from datetime import timedelta

            start_dt = utils.str2date(START_DT)
            
            if value == 'MTD':
                start_dt = end_dt.replace(day=1)
            elif value == 'WTD':
                start_dt = end_dt - timedelta(days=end_dt.weekday())
            elif value == 'YTD':
                start_dt = end_dt.replace(month=1, day=1) 
            
            if start_dt < utils.str2date(START_DT):
                start_dt = utils.str2date(START_DT)

            start_dt = utils.date2str(start_dt)
            end_dt = utils.date2str(end_dt)

            return get_visual_data(start_dt, end_dt, args.db_path)['fig_nav']
        else:
            return get_visual_data(start_date, end_date, args.db_path)['fig_nav']

    @app.callback(
        Output('v_pie_id', 'figure'),
        Input('roi_range', 'start_date'),
        Input('roi_range', 'end_date'))
    def update_v_pie(start_date, end_date):
        return get_visual_data(start_date, end_date, args.db_path)['fig_v_pie']
    

    @app.callback(
        Output('c_pie_id', 'figure'),
        Input('roi_range', 'start_date'),
        Input('roi_range', 'end_date'))
    def update_v_pie(start_date, end_date):
        return get_visual_data(start_date, end_date, args.db_path)['fig_c_pie']

    app.layout = get_default_page()

    app.run_server(debug=True)