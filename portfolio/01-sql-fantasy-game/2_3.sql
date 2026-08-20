SELECT
    items.game_items,
    COUNT(events.transaction_id),
    COUNT(events.transaction_id)::REAL / SUM(COUNT(events.transaction_id)) OVER () AS  t_share,
    COUNT(DISTINCT events.id)::REAL / (SELECT COUNT(DISTINCT id) FROM fantasy.events WHERE amount > 0) AS u_share
FROM fantasy.events
JOIN fantasy.items ON events.item_code = items.item_code
WHERE events.amount > 0
GROUP BY items.game_items
ORDER BY u_share DESC;