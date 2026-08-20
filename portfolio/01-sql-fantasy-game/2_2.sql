SELECT
    COUNT(*),
    COUNT(*)::REAL / (SELECT COUNT(*) 
    				  FROM fantasy.events)
FROM fantasy.events
WHERE amount = 0;