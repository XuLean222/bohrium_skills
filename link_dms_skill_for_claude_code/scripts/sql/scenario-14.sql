SELECT 
    *
FROM 
    `sigma-search`.`hot_session`
WHERE 
    `create_time` >= '2026-03-31 00:00:00' 
    and `create_time` < '2026-04-01 00:00:00' 
    AND `title` != '' 
    AND `scene` = 'adk_science_navigator'
    AND `user_id` != '14329'
    and `user_id` != '897445'
