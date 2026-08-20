/* Проект «Разработка витрины и решение ad-hoc задач»
 * Цель проекта: подготовка витрины данных маркетплейса «ВсёТут»
 * и решение четырех ad hoc задач на её основе
 * 
 * Автор: Тарасов Иван
 * Дата: 28.12.2025
*/



-- Часть 1. Разработка витрины 
/* Заметил что оценка пользователя имеет странные значения (
1,2,3,4,5
10,20,30,40,50
При создании витрины нужно это учесть и делить на 10 в случае необходимости 
)
*/
WITH payments_agg AS (
    SELECT
        order_id,
        MAX(CASE WHEN payment_installments > 1 THEN 1 ELSE 0 END) AS has_installments,
        MAX(CASE WHEN payment_type = 'промокод' THEN 1 ELSE 0 END) AS has_promo,
        MAX(CASE WHEN payment_type = 'денежный перевод' THEN 1 ELSE 0 END) AS has_money_transfer
    FROM ds_ecom.order_payments
    GROUP BY order_id
),
order_reviews_processed AS (
    SELECT
        order_id,
        AVG(
            CASE
                WHEN review_score > 5 THEN review_score / 10.0
                ELSE review_score
            END
        ) AS avg_order_rating
    FROM ds_ecom.order_reviews
    GROUP BY order_id
),
product_user_features AS (
    SELECT
        u.user_id,
        u.region,
        MIN(o.order_approved_at) AS first_order_ts,
        MAX(o.order_approved_at) AS last_order_ts,
        COUNT(DISTINCT o.order_id) AS total_orders,
        AVG(r.avg_order_rating) AS avg_order_rating,
        COUNT(DISTINCT CASE WHEN r.avg_order_rating IS NOT NULL THEN o.order_id END) AS num_orders_with_rating,
        COUNT(DISTINCT CASE WHEN o.order_status = 'Отменено' THEN o.order_id END) AS num_canceled_orders,
        SUM(CASE WHEN o.order_status = 'Доставлено' THEN o_it.order_total_cost ELSE 0 END) AS total_order_costs,
        AVG(CASE WHEN o.order_status = 'Доставлено' THEN o_it.order_total_cost END) AS avg_order_cost,
        COUNT(DISTINCT CASE WHEN p.has_installments = 1 THEN o.order_id END) AS num_installment_orders,
        COUNT(DISTINCT CASE WHEN p.has_promo = 1 THEN o.order_id END) AS num_orders_with_promo,
        MAX(p.has_money_transfer) AS used_money_transfer,
        MAX(p.has_installments) AS used_installments,
        MAX(CASE WHEN o.order_status = 'Отменено' THEN 1 ELSE 0 END) AS used_cancel
    FROM ds_ecom.users u
    JOIN ds_ecom.orders o ON o.buyer_id = u.buyer_id
    JOIN (
        SELECT
            order_id,
            SUM(price + delivery_cost) AS order_total_cost
        FROM ds_ecom.order_items
        GROUP BY order_id
    ) o_it ON o_it.order_id = o.order_id
    LEFT JOIN order_reviews_processed r ON r.order_id = o.order_id
    LEFT JOIN payments_agg p ON p.order_id = o.order_id
    WHERE o.order_status IN ('Доставлено', 'Отменено')
    GROUP BY u.user_id, u.region
)
SELECT
    user_id,
    region,
    first_order_ts,
    last_order_ts,
    last_order_ts - first_order_ts AS lifetime,
    total_orders,
    avg_order_rating,
    num_orders_with_rating,
    num_canceled_orders,
    CASE
        WHEN total_orders > 0
        THEN num_canceled_orders::REAL / total_orders
        ELSE 0
    END AS canceled_orders_ratio,
    total_order_costs,
    avg_order_cost,
    num_installment_orders,
    num_orders_with_promo,
    used_money_transfer,
    used_installments,
    used_cancel
FROM product_user_features
WHERE region IN (
    SELECT region
    FROM product_user_features
    GROUP BY region
    ORDER BY SUM(total_orders) DESC
    LIMIT 3
);

-- Часть 2. Решение ad hoc задач


/* Задача 1. Сегментация пользователей 
 * Разделение пользователей на группы по количеству совершённых ими заказов.
 * Подсчитать для каждой группы общее количество пользователей,
 * среднее количество заказов, среднюю стоимость заказа.
*/

SELECT
    CASE
        WHEN total_orders = 1 THEN '1'
        WHEN total_orders BETWEEN 2 AND 5 THEN '2'
        WHEN total_orders BETWEEN 6 AND 10 THEN '3'
        ELSE '4'
    END AS user_segment,
    COUNT(DISTINCT user_id) AS users_cnt,
    COUNT(DISTINCT CASE WHEN num_orders_with_promo = 1 THEN user_id END) AS users_cnt_promo,
    COUNT(DISTINCT user_id)::REAL / sum(COUNT(DISTINCT user_id)) over() AS ratio,
    AVG(total_orders) AS avg_orders_cnt,
    AVG(avg_order_cost) AS avg_order_cost
FROM ds_ecom.product_user_features
GROUP BY user_segment;

/*краткий комментарий с выводами по результатам задачи 1.
 1)Большинство пользователей делает 1 заказ(96%) не решаясь на второй,
 можно рассмотреть возможность стимулировать пользователей совершать 2 заказ за счет выдачи промокодов на 2 заказ,
 2)в данной статистике много пользователей делает только 1 заказ, но мало кто из них делает это за счет возможного
 приветственного промокода так как на 60473 первых заказов только 1727 сделано с промокодом, значит возможно они нашли более удачную постоянную альтернативу.
*/



/* Задача 2. Ранжирование пользователей 
 * Отсортировать пользователей, сделавших 3 заказа и более, по убыванию среднего чека покупки.  
 * Вывести 15 пользователей с самым большим средним чеком среди указанной группы.
*/

SELECT
    user_id,
    region,
    total_orders,
    avg_order_cost
FROM ds_ecom.product_user_features
WHERE total_orders >= 3 AND canceled_orders_ratio < 1 
ORDER BY avg_order_cost DESC
LIMIT 15;

/* краткий комментарий с выводами по результатам задачи 2.
  Существует отличающуеся от других данные по среднему чеку(28070.00, 14716.67, 12478.33 ...) которые сильно привышают медиану,
  есть смысл выборочно изучить некоторые из них, чтобы узнать, что стимулировало людей совершивших эту покупку.
*/



/* Задача 3. Статистика по регионам. 
 * Для каждого региона подсчитать:
 * - общее число клиентов и заказов;
 * - среднюю стоимость одного заказа;
 * - долю заказов, которые были куплены в рассрочку;
 * - долю заказов, которые были куплены с использованием промокодов;
 * - долю пользователей, совершивших отмену заказа хотя бы один раз.
*/

SELECT
    region,
    COUNT(DISTINCT user_id) AS users_cnt,
    SUM(total_orders) AS orders_cnt,
    AVG(avg_order_cost) AS avg_order_cost,
    AVG(CASE WHEN total_orders > 0 THEN num_installment_orders::REAL / total_orders ELSE 0 END) AS installment,
    AVG(CASE WHEN total_orders > 0 THEN num_orders_with_promo::REAL / total_orders ELSE 0 END) AS promo,
    AVG(used_cancel::REAL) AS with_cancel
FROM ds_ecom.product_user_features
GROUP BY region;

/*комментарий с выводами по результатам задачи 3.
 Данные по количеству пользователей не сильно разнется, т.к. Москва по статистике должна обладать куда более внушительным количеством пользователей и заказов, 
 но несмотря на большее количество пользователей, в Москве средние траты на заказ ниже(<14% СПБ).
*/



/* Задача 4. Активность пользователей по первому месяцу заказа в 2023 году
 * Разбить пользователей на группы в зависимости от того, в какой месяц 2023 года они совершили первый заказ.
 * Для каждой группы посчитать:
 * - общее количество клиентов, число заказов и среднюю стоимость одного заказа;
 * - средний рейтинг заказа;
 * - долю пользователей, использующих денежные переводы при оплате;
 * - среднюю продолжительность активности пользователя.
*/

SELECT
    EXTRACT(MONTH FROM first_order_ts) AS first_order_month,
    COUNT(DISTINCT user_id) AS users_cnt,
    SUM(total_orders) AS orders_cnt,
    AVG(avg_order_cost) AS avg_order_cost,
    AVG(avg_order_rating) AS avg_order_rating,
    AVG(used_money_transfer::REAL) AS money_transfer_users_ratio,
    AVG(lifetime) AS avg_lifetime_days
FROM ds_ecom.product_user_features
WHERE EXTRACT(YEAR FROM first_order_ts) = 2023
GROUP BY first_order_month;

/* краткий комментарий с выводами по результатам задачи 4
рост числа новых пользователей в течение года, с наибольшим притоком в ноябре.
Увелечение количество заказов в основном соответствует увелечению количества пользователей.
Самый высокий средний рейтинг заказов август (4.31), самый низкий ноябрь (4.00) по мере увелечения пользователей оценка слегка снижается
среднее время жизни пользователя в течение года сильно уменьшилось: январь 13 дней, декабрь 2 дня.
 * 