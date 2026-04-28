-- 查询新版SN的点赞和点踩
SELECT * FROM `common_feed_back_log`  
  where `scene`  = 'science_navigator'
  AND create_time >= '2026-03-31 00:00:00' 
  AND `create_time` < '2026-04-01 00:00:00'
  AND (`reaction_type` = 2 or `reaction_type` = 1)
  and `status` = 1;
