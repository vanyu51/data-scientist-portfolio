"""
DAG для batch-инференса продаж "Прилавок"
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.models import Variable
from airflow.hooks.postgres_hook import PostgresHook
import pandas as pd
import numpy as np
import boto3
from catboost import CatBoostRegressor
import logging
import io
import pickle

# ========== Функция предобработки данных ==========
from preprocessing import preprocess_data, FEATURES

# ========== Конфигурация ==========

S3_BUCKET = Variable.get("s3_bucket_name", default_var="your-bucket-name")
S3_ACCESS_KEY = Variable.get("s3_access_key", default_var=None)
S3_SECRET_KEY = Variable.get("s3_secret_key", default_var=None)
S3_MODEL_KEY = Variable.get("s3_model_key", default_var="catboost_sales_model.pkl")

POSTGRES_CONN_ID = "postgres_sales_db"  # ID подключения в Airflow Connections

RANDOM_STATE = 42
CAT_FEATURES = ['store', 'dept', 'is_holiday', 'type']

LAG_FEATURES = [
    'avg_sales_before', 'sales_1week_ago', 'sales_2week_ago', 'sales_4week_ago',
    'mean_sales_2week', 'mean_sales_4week',
]
MODEL_PATH = '/tmp/catboost_model.pkl'

logger = logging.getLogger(__name__)


# ========== Задачи DAG ==========

def load_data_from_postgres(**context):
    """
    Загрузка данных для инференса из Postgres.
    Загружаем таблицы plan, stores, features и исторические продажи для расчета лаговых признаков.
    
    Передавать большие данные через xcom_push нельзя!
    Поэтому в данной функции создайте таблицу, которую будем использовать для предобработки данных (назовем ее inference_data_temp).
    В этой таблице соберите исторические данные (до первой даты плана), а также плановые данные (столбец weekly_sales заполните null).
    Здесь же соберите признаки из всех необходимых таблиц воедино.

    После создания выведите информацию (можно через print(), можно через logging.info):
    - количество строк в полученной таблице
    - минимальная дата
    - максимальная дата

    В XCom передайте первую дату плана (по ней будем разделять все данные на обучающие и инференс).
    
    """
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)

    first_plan_date = hook.get_first("SELECT MIN(date) FROM plan")[0]

    # история до начала плана + план с пустыми продажами, к ним присоединяем признаки
    hook.run("DROP TABLE IF EXISTS inference_data_temp")
    hook.run(
        """
        CREATE TABLE inference_data_temp AS
        WITH combined AS (
            SELECT store, dept, date, weekly_sales, is_holiday
            FROM sales
            WHERE date < %(first_plan_date)s
            UNION ALL
            SELECT store, dept, date, NULL::DOUBLE PRECISION AS weekly_sales, is_holiday 
            FROM plan
        )
        SELECT
            c.store, c.dept, c.date, c.weekly_sales, c.is_holiday,
            s.type, s.size,
            f.temperature, f.fuel_price,
            f.factor1, f.factor2, f.factor3, f.factor4, f.factor5,
            f.cpi, f.unemployment
        FROM combined c
        LEFT JOIN stores s ON c.store = s.store
        LEFT JOIN features f ON c.store = f.store AND c.dept = f.dept AND c.date = f.date
        """,
        parameters={'first_plan_date': first_plan_date},
    )
    # NULL::DOUBLE PRECISION AS weekly_sales - будущая целевая переменная
    rows, min_date, max_date = hook.get_first("SELECT COUNT(*), MIN(date), MAX(date) FROM inference_data_temp")
    print("Таблица inference_data_temp", rows, "строк")
    print("Минимальная дата:", min_date)
    print("Максимальная дата:", max_date)

    context['ti'].xcom_push(key='first_plan_date', value=str(first_plan_date)) ## context['ti'] - объект текущей задачи (через него работаем с xcom) можно класть и забирать значения через pull push по key


def preprocess_features(**context):
    """
    Предобработка признаков для инференса.
    
    1. Читаем первую дату плана из XCom
    2. Читаем данные из таблицы inference_data_temp
    3. Выполняем предобработку признаков (функция preprocess_data)
    4. Оставляем только строки, относящиеся к плану (дату берем из п.1)
    5. Не забудьте удалить колонку weekly_sales (здесь она всегда будет заполнена null)
    6. Лаговые переменные для первых недель стоит заполнить нулями.
    7. Удаляем строки с оставшимися NaN
    8. Передаем датафрейм в XCom (теперь он уже небольшой)
    9. Удалим нашу временную таблицу inference_data_temp из БД
    """
    first_plan_date = context['ti'].xcom_pull(key='first_plan_date', task_ids='load_data')
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)

    df = hook.get_pandas_df("SELECT * FROM inference_data_temp") # аналог чтения sql в pandas)

    df = preprocess_data(df)

    df = df[df['date'] >= pd.to_datetime(first_plan_date)]
    df = df.drop(columns=['weekly_sales'])
    df[LAG_FEATURES] = df[LAG_FEATURES].fillna(0)

    df = df[['date'] + FEATURES].dropna().reset_index(drop=True)

    context['ti'].xcom_push(key='inference_data', value=df.to_json(orient='records', date_format='iso'),)

    hook.run("DROP TABLE IF EXISTS inference_data_temp")


def load_model_from_s3(**context):
    """
    Загрузка обученной модели CatBoost из S3 (Yandex Cloud) через pickle.

    Клиент уже создан для вас. Необходимо загрузить модель используя io.BytesIO().
    Сохраните модель во временный файл для передачи через XCom.
    В XCom передайте путь до модели.
    """
    s3_client = boto3.client(
        's3',
        endpoint_url='https://storage.yandexcloud.net',
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name='ru-central1',
    )

    filebuffer = io.BytesIO()
    s3_client.download_fileobj(S3_BUCKET, S3_MODEL_KEY, filebuffer)
    filebuffer.seek(0)
    model = pickle.load(filebuffer)

    with open(MODEL_PATH, 'wb') as f: #пишем модель(w) которая созраняется в бинарной форме(b)
        pickle.dump(model, f)

    context['ti'].xcom_push(key='model_path', value=MODEL_PATH)


def run_batch_inference(**context):
    """
    Batch-инференс: применение модели к подготовленным данным.

    1. Из XCom загрузите подготовленный датафрейм для инференса и путь к обученной модели.
    2. Прочитайте датафрейм используя pandas
    3. Загрузите модель из pickle файла
    4. Выполните predict
    5. Сохраните предсказания в качестве нового столбца - predicted_weekly_sales
    6. Обработайте аномальные предсказания (замените на 0)
    7. Передайте в XCom датафрейм с предсказаниями (используйте .to_json())
    """
    ti = context['ti']
    data_json = ti.xcom_pull(key='inference_data', task_ids='preprocess_features')
    model_path = ti.xcom_pull(key='model_path', task_ids='load_model')

    df = pd.read_json(io.StringIO(data_json), orient='records')

    with open(model_path, 'rb') as f: #читаем модель(r) которая созранена в бинарной форме(b)
        model = pickle.load(f)

    X = df[model.feature_names_]
    df['predicted_weekly_sales'] = model.predict(X)

    df['predicted_weekly_sales'] = np.clip(df['predicted_weekly_sales'], 0, None) # замена предсказаний меньше 0 на 0

    result = df[['store', 'dept', 'date', 'predicted_weekly_sales']]
    ti.xcom_push(key='predictions', value=result.to_json(orient='records', date_format='iso'),)


def save_predictions_to_postgres(**context):
    """
    Запись результатов предсказаний в таблицу predictions в Postgres.

    1. Загрузите датафрейм с предсказаниями из XCom
    2. Подключение к БД, создание таблицы, вставка данных уже реализованы
    3. Выведите через print или logging.info количество строк итоговой таблицы и первые 5 строк.
    """
    predictions_json = context['ti'].xcom_pull(key='predictions', task_ids='run_inference')
    predictions_df = pd.read_json(io.StringIO(predictions_json))
    predictions_df['date'] = pd.to_datetime(predictions_df['date']).dt.date

    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)

    hook.run("DROP TABLE IF EXISTS predictions;")

    hook.run("""
    CREATE TABLE IF NOT EXISTS predictions (
        store INT,
        dept INT,
        date DATE,
        predicted_weekly_sales FLOAT,
        prediction_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (store, dept, date)
    );
    """)

    # to_dict превращает numpy-типы в обычные python-типы, иначе БД их не примет
    targets = ['store', 'dept', 'date', 'predicted_weekly_sales']
    rows = [tuple(row.values()) for row in predictions_df[targets].to_dict('records')]
    hook.insert_rows(table='predictions', rows=rows, target_fields=targets, commit_every=10000)

    count = hook.get_first("SELECT COUNT(*) FROM predictions;")[0]
    print("Строк записано строк:", count)

    head = hook.get_pandas_df("SELECT * FROM predictions ORDER BY date, store, dept LIMIT 5;")
    print("Первые 5 строк:", head.to_string())




default_args = {
    'owner': 'Тарасов Иван Сергеевич',
    'depends_on_past': False,
    'email': ['ivantarasoff100500@gmail.com'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}
dag = DAG(
    'sales_prediction_batch_inference',
    default_args=default_args,
    description='Batch-инференс прогнозирования продаж для Прилавка',
    schedule_interval='0 20 * * 0',  # Каждое воскресенье в 20:00
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['sales', 'ml', 'batch-inference', 'production'],
)

task_preprocess = PythonOperator(
    task_id='preprocess_features',
    python_callable=preprocess_features,
    provide_context=True,
    dag=dag,
)

task_inference = PythonOperator(
    task_id='run_inference',
    python_callable=run_batch_inference,
    provide_context=True,
    dag=dag,
)

task_load_data = PythonOperator(
    task_id='load_data',
    python_callable=load_data_from_postgres,
    provide_context=True,
    dag=dag,
)

task_load_model = PythonOperator(
    task_id='load_model',
    python_callable=load_model_from_s3,
    provide_context=True,
    dag=dag,
)

task_save_predictions = PythonOperator(
    task_id='save_predictions',
    python_callable=save_predictions_to_postgres,
    provide_context=True,
    dag=dag,
)

task_load_data >> task_preprocess
task_load_model >> task_inference
task_preprocess >> task_inference >> task_save_predictions
