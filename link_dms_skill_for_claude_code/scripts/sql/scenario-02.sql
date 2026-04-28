SELECT  
  *
FROM 
  `user_behavior_record`
WHERE 
  `scene` = 'feedback' 
  And `create_time` > '2025-12-01 00:00:00' 
  AND `create_time` < '2025-12-08 00:00:00'
