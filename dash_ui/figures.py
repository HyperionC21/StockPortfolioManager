import pandas as pd
import numpy as np
import plotly.express as px

from backend import base, reporting
from utils import utils



def get_evolution(start_dt, end_dt, db_path):
    db_connector = base.BaseDBConnector(db_path)
    db_fetcher = base.DataFetcher(db_connector)
    reporter = reporting.Reporter(db_fetcher)
   
    ref_profit = reporter.get_portfolio_info(1, start_dt)['profit']
    ref_cost =  reporter.get_portfolio_info(1, end_dt)['cost']

    df_evolution = pd.DataFrame()
    df_evolution['DT'] = list(utils.daterange(start_dt, end_dt))
    df_evolution['PROFIT'] = df_evolution['DT'].apply(lambda x: reporter.get_portfolio_info(1, x)['profit']) - ref_profit
    df_evolution['COST'] = df_evolution['DT'].apply(lambda x: reporter.get_portfolio_info(1, x)['cost'])

    df_evolution['NAV'] = df_evolution['PROFIT'] + ref_cost

    df_evolution['RETURN'] = np.round(df_evolution['PROFIT'] * 100 / ref_cost, 2)

    return df_evolution

def get_composition(ref_date, db_path, oth_thresh=2):
    db_connector = base.BaseDBConnector(db_path)
    db_fetcher = base.DataFetcher(db_connector)
    reporter = reporting.Reporter(db_fetcher)

    ref_cost = reporter.get_portfolio_info(1, ref_date)['cost']

    df_composition = reporter.get_portfolio_info(1, ref_date)['df']
    df_composition['PROFIT'] = np.round(df_composition['VALUE'] - df_composition['TOTAL_COST'], 0)
    df_composition['PROFIT%'] = np.round(df_composition['PROFIT'] * 100 / df_composition['TOTAL_COST'], 2)
    df_composition['VALUE%'] = np.round(df_composition['VALUE'] * 100 / df_composition['VALUE'].sum(), 2)

    df_composition['VALUE'] = np.round(df_composition['VALUE'], 0)
    df_composition['FX'] = np.round(df_composition['FX'], 2)

    df_composition['TOTAL_COST'] = df_composition['TOTAL_COST'].astype(int)
    df_composition['PRICE'] = df_composition['PRICE'].apply(lambda x: np.round(x, 2))

    df_comp_oth = df_composition[df_composition['VALUE%'] <= oth_thresh]
    df_composition = df_composition[df_composition['VALUE%'] > oth_thresh]

    def oth_gr_func(df):
        res = {}

        res['N_SHARES'] = np.nan
        res['TOTAL_COST'] = df['TOTAL_COST'].sum()
        res['PRICE'] = np.round((df['PRICE'] * df['N_SHARES']).sum() / df['N_SHARES'].sum(), 0)
        res['FX'] = np.nan
        res['VALUE'] = df['VALUE'].sum()
        res['PROFIT'] = df['PROFIT'].sum()
        res['PROFIT%'] = np.round((res['VALUE'] - res['TOTAL_COST']) * 100 / res['TOTAL_COST'], 2)
        res['VALUE%'] = df['VALUE%'].sum()

        return pd.Series(index=['N_SHARES', 'TOTAL_COST', 'PRICE', 'FX', 'VALUE', 'PROFIT', 'PROFIT%', 'VALUE%'], data=res)

    df_comp_oth['TICKER'] = 'OTHER'

    df_comp_oth = df_comp_oth.groupby(['TICKER', 'DT']).apply(oth_gr_func).reset_index()


    df_composition = pd.concat([df_composition, df_comp_oth], axis=0)
    df_composition = df_composition.sort_values(by='VALUE', ascending=False)
    return df_composition.drop_duplicates()

def get_visual_data(start_dt, end_dt, db_path):
    df_ev = get_evolution(start_dt, end_dt, db_path=db_path)
    df_comp = get_composition(end_dt, db_path=db_path)

    fig_roi = px.line(df_ev, x='DT', y=['RETURN'])
    fig_nav = px.line(df_ev, x='DT', y=['NAV'])
    graph_profit = px.line(df_ev, x='DT', y=['PROFIT'])

    fig_value_pie = px.pie(df_comp, names='TICKER', values='VALUE', title='Portfolio value')
    fig_cost_pie = px.pie(df_comp, names='TICKER', values='TOTAL_COST', title='Portfolio invested')

    fig_profit_perc = px.bar(df_comp.sort_values(by='PROFIT%', ascending=False), \
        x='TICKER', y='PROFIT%', color='TICKER', title='Percentage profit')
    fig_profit = px.bar(df_comp.sort_values(by='PROFIT', ascending=False), \
        x='TICKER', y='PROFIT', color='TICKER', title='Absolute profit')

    return {
        'ev' : df_ev,
        'comp' : df_comp,
        'fig_roi' : fig_roi,
        'fig_nav' : fig_nav,
        'graph_profit' : graph_profit,
        'fig_v_pie' : fig_value_pie,
        'fig_c_pie' : fig_cost_pie,
        'fig_pr_perc' : fig_profit_perc,
        'fig_pr' : fig_profit
    }