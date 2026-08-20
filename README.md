# Портфолио проектов по Data Science

Vои проекты по пути от SQL к ML от агрегатных запросов до бустингов с калибровкой вероятностей и объяснением предсказаний через SHAP. Каждая папка отдельный проект со своим README, где описан подход.

## Оглавление

### SQL
- [01 — Аналитика монетизации в игре](./01-sql-fantasy-game) — CTE, оконные функции
- [02 — Витрина данных маркетплейса](./02-sql-marketplace-datamart) — 4 ad hoc задачи, создание витрины данных

### Анализ данных (EDA / pandas)
- [03 — Факторы повторных покупок](./03-eda-afisha-loyalty) — SQL + pandas, `phik`-корреляция
- [04 — Рынок общепита](./04-eda-restaurants-moscow) — EDA по 8 бизнес-вопросам
- [05 — Предобработка данных о продажах игр](./05-eda-games-sales-preprocessing) — работа со скрытыми пропусками и дубликатами

### Machine Learning
- [06 — Предсказание массы животного](./06-ml-linear-turtle-weight) — линейная регрессия, Lasso/Ridge/SGD
- [07 — Прогноз оттока клиентов](./07-ml-classification-coffee-churn) — классификация с сильным дисбалансом, PR-AUC
- [08 — Классификация возрастной группы](./08-ml-classification-age-group) — мультикласс, отбор признаков (SelectKBest/RFE)
- [09 — Прогноз CTR рекламы](./09-ml-classification-ad-ctr) — SVC, калибровка вероятностей (Brier/ECE/MCE)
- [10 — Кредитный скоринг](./10-ml-credit-scoring) — временные ряды, Optuna, кастомные бизнес-метрики
- [11 — Оценка стоимости автомобиля](./11-ml-car-price-boosting) — XGBoost/CatBoost/LightGBM, SHAP
- [12 — Прогноз спроса на прокат велосипедов](./12-ml-bike-demand-nonlinear) — KNN, Decision Tree, Optuna
- [13 — Прогноз отмены бронирования отеля](./13-ml-hotel-booking-cancellation) — NLP (TF-IDF), экономическая метрика IR, бустинг
- [14 — Риск задержки доставки](./14-ml-clustering-delivery-risk) — классификация + K-Means, t-SNE

## Стек

**Python:** pandas, numpy, scikit-learn, CatBoost, XGBoost, LightGBM, Optuna, SHAP, phik, imbalanced-learn
**SQL:** PostgreSQL (CTE, оконные функции, агрегация)
**Визуализация:** matplotlib, seaborn

## О подходе

В каждом проекте старался идти от постановки задачи и EDA до подбора гиперпараметров, интерпретации модели и иногда перевода метрик качества в бизнес-язык.
