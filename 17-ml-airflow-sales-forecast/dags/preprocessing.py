import pandas as pd
import numpy as np

import logging
logger = logging.getLogger(__name__)


TARGET = 'weekly_sales'
KEY = ['store', 'dept', 'date']
CAT_FEATURES = ['store', 'dept', 'type']

FEATURES = [
    'store', 'dept', 'is_holiday', 'type', 'size', 'month', 'quarter',
    'avg_sales_before', 'sales_1week_ago', 'sales_2week_ago', 'sales_4week_ago',
    'mean_sales_2week', 'mean_sales_4week', 'day_of_year', 'weeks_to_new_year',
]

TRAIN_END = '2025-09-01'
VAL_END = '2025-10-31'


def merge_data(sales, features, stores):
    return sales.merge(features, on=KEY, how='left').merge(stores, on='store', how='left')


def no_negative_sales(df):
    df = df.copy()
    df.loc[df[TARGET] < 0, TARGET] = 0
    return df


def create_temporal_features(df):
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.month
    df['quarter'] = df['date'].dt.quarter
    df['year'] = df['date'].dt.year
    df['day_of_year'] = df['date'].dt.dayofyear
    df['weeks_to_new_year'] = (365 - df['day_of_year']) // 7
    return df

def create_avg_sales_feature(df):
    df = df.copy().sort_values(KEY)
    grouped = df.groupby(['store', 'dept'])[TARGET]
    df['avg_sales_before'] = grouped.transform(lambda x: x.shift(1).expanding().mean())
    return df

def create_lag_features(df):
    df = df.copy().sort_values(KEY)
    grouped = df.groupby(['store', 'dept'])[TARGET]
    df['sales_1week_ago'] = grouped.shift(1)
    df['sales_2week_ago'] = grouped.shift(2)
    df['sales_4week_ago'] = grouped.shift(4)
    return df

def create_rolling_features(df):
    df = df.copy().sort_values(KEY)
    grouped = df.groupby(['store', 'dept'])[TARGET]
    df['mean_sales_2week'] = grouped.transform(lambda x: x.shift(1).rolling(window=2, min_periods=1).mean())
    df['mean_sales_4week'] = grouped.transform(lambda x: x.shift(1).rolling(window=4, min_periods=1).mean())
    return df

def preprocess_data(df):
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])

    df = no_negative_sales(df)
    df = create_temporal_features(df)
    df = create_avg_sales_feature(df)
    df = create_lag_features(df)
    df = create_rolling_features(df)

    df[CAT_FEATURES] = df[CAT_FEATURES].astype('category')

    logger.info(f'Предобработка завершена: {df.shape[0]} строк, {df.shape[1]} колонок')
    return df.sort_values(KEY).reset_index(drop=True)


def split_train_val(df):
    df = df.sort_values('date').reset_index(drop=True)
    train = df[df['date'] < TRAIN_END]
    val = df[(df['date'] >= TRAIN_END) & (df['date'] <= VAL_END)]
    return train, val
