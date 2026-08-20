WITH user_counts AS (
    SELECT COUNT(*) AS total_users,
           COUNT(CASE WHEN payer = 1 THEN 1 END) AS payer_users
    FROM fantasy.users
)
SELECT total_users,
       payer_users,
       payer_users::REAL / total_users 
FROM user_counts;