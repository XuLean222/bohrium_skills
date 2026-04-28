SELECT *
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (PARTITION BY uuid ORDER BY create_time DESC) AS rn
    FROM `hot_session`
    WHERE 
        `create_time` > '2025-12-28 10:00:00' 
        AND `create_time` < '2025-12-28 16:00:00' 
        AND `title` != '' 
        AND `scene` = 'paper'
) t
WHERE t.rn = 1
LIMIT 200;
