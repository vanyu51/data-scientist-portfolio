WITH payer_byRace AS (
    SELECT r.race, 
    	   COUNT(*) AS race_users,
           COUNT(CASE WHEN payer = 1 THEN 1 END) AS payer_users
    FROM fantasy.users
    JOIN fantasy.race AS r ON r.race_id = users.race_id
    GROUP BY r.race 
)
SELECT race,
       race_users,
       payer_users,
       payer_users::REAL / race_users  
FROM payer_byRace;