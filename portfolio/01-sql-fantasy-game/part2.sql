WITH race_stats AS (
    SELECT r.race,
           COUNT(DISTINCT u.id) AS user_count,
           COUNT(DISTINCT CASE WHEN u.payer = 1 AND e.id IS NOT NULL THEN u.id END) AS payer_count,
           SUM(e.amount) AS amount,
           COUNT(DISTINCT e.id) AS with_transaction,
           COUNT(e.transaction_id) AS total_transaction
    FROM fantasy.users AS u
    LEFT JOIN fantasy.events AS e ON e.id = u.id AND e.amount > 0
    JOIN fantasy.race AS r ON r.race_id = u.race_id 
    GROUP BY r.race
)
SELECT race,
       user_count,
       with_transaction,
       with_transaction::REAL / user_count AS unknown,
       payer_count::REAL / user_count AS conversion_rate,
       payer_count::REAL / with_transaction AS payer_share,
       total_transaction::REAL / with_transaction AS avg_per_buyer,
       amount::REAL / total_transaction AS avg_total,
       amount::REAL / with_transaction AS avg_transaction
FROM race_stats;