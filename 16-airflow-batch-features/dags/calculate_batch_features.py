from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

def load_data(connection_string):
    engine = create_engine(connection_string)

    customers = pd.read_sql_query('SELECT * FROM customers', engine)
    sessions = pd.read_sql_query('SELECT * FROM sessions', engine)
    events = pd.read_sql_query('SELECT * FROM events', engine)
    orders = pd.read_sql_query('SELECT * FROM orders', engine)

    return customers, sessions, events, orders

def preprocessing(customers, sessions, events, orders):
    customers['signup_date'] = pd.to_datetime(customers['signup_date'])
    sessions['start_time'] = pd.to_datetime(sessions['start_time'])
    events['timestamp'] = pd.to_datetime(events['timestamp'])
    orders['order_time'] = pd.to_datetime(orders['order_time'])

    events = events.drop_duplicates(subset=['event_id'])
    orders = orders.drop_duplicates(subset=['order_id'])

    orders['total_usd'] = pd.to_numeric(orders['total_usd'], errors='coerce').fillna(0.0)

    return customers, sessions, events, orders

def time_window(sessions, events, orders, run_date):
    ses = sessions[sessions['start_time'] < run_date].copy()
    ev = events[events['timestamp'] < run_date].copy()
    ors = orders[orders['order_time'] < run_date].copy()

    ev = ev.merge(ses[['session_id', 'customer_id']], on='session_id', how='inner')

    return ses, ev, ors

def add_event_features(feats, ev, ses, run_date, days):
    before = run_date - timedelta(days=days)
    ev_before = ev[ev['timestamp'] >= before]
    ses_before = ses[ses['start_time'] >= before]

    agg = ev_before.pivot_table(index='customer_id', columns='event_type', values='event_id', aggfunc='count')
    agg = agg.reindex(columns=['page_view', 'add_to_cart', 'purchase'])
    agg['unique_products'] = ev_before.groupby('customer_id')['product_id'].nunique()
    agg['sessions'] = ses_before.groupby('customer_id').size()

    feats = feats.merge(agg.add_suffix(f'_{days}d'), left_on='customer_id', right_index=True, how='left').fillna(0)

    return feats

def add_conversion_features(feats, days):
    feats[f'cr_view_to_cart_{days}d'] = (feats[f'add_to_cart_{days}d'] / feats[f'page_view_{days}d']).replace([np.inf, np.nan], 0.0)
    feats[f'cr_cart_to_purchase_{days}d'] = (feats[f'purchase_{days}d'] / feats[f'add_to_cart_{days}d']).replace([np.inf, np.nan], 0.0)
    feats = feats.drop(columns=[f'purchase_{days}d'])

    return feats

def add_session_features(feats, ses, ev, before_30d):
    s = ses[ses['start_time'] >= before_30d].copy()
    s['dur'] = (s['session_id'].map(ev.groupby('session_id')['timestamp'].max()) - s['start_time']).dt.total_seconds().fillna(0)
    feats['avg_session_seconds_30d'] = feats['customer_id'].map(s.groupby('customer_id')['dur'].mean()).fillna(0.0)

    return feats

def add_order_features(feats, ors, run_date, before_30d):
    o = (ors[ors['order_time'] >= before_30d].groupby('customer_id')['total_usd'].agg(orders_30d='count', total_usd_sum_30d='sum', total_usd_avg_30d='mean'))
    feats = feats.merge(o, left_on='customer_id', right_index=True, how='left').fillna(0)

    last = ors.groupby('customer_id')['order_time'].max()
    feats['days_since_last_order'] = (run_date - feats['customer_id'].map(last)).dt.days.fillna(-1).astype(int)

    return feats

def batch_features(customers, sessions, events, orders, run_date):
    run_date = pd.to_datetime(run_date)
    before_30d = run_date - timedelta(days=30)

    customers, sessions, events, orders = preprocessing(customers, sessions, events, orders)
    ses, ev, ors = time_window(sessions, events, orders, run_date)

    feats = customers[customers['signup_date'] < run_date][['customer_id']].copy()
    feats['run_date'] = run_date

    for days in (7, 30):
        feats = add_event_features(feats, ev, ses, run_date, days)
        feats = add_conversion_features(feats, days)

    feats = add_session_features(feats, ses, ev, before_30d)
    feats = add_order_features(feats, ors, run_date, before_30d)

    return feats

def save_features(feats, local_path):
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    feats.to_csv(local_path, index=False)
    return str(local_path)