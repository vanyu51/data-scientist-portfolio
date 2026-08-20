SELECT COUNT(*),
       SUM(amount),
       MIN(amount),
       MAX(amount),
       AVG(amount),
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount),
       STDDEV_POP(amount)
FROM fantasy.events;