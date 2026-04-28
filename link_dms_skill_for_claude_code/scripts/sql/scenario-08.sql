SELECT
  sr.`user_id`,
  sr.`reason`,
  ss.`id` session_id,  
  ss.`title`,
  ss.`create_time`,
  COALESCE(NULLIF(ss.meta ->> '$.source', ''), '(empty)') AS openai_source,
  CASE
    WHEN DATE(hq.create_time) = DATE(u.create_time) THEN '注册首日提问'
    WHEN u.create_time < '2025-10-31 23:59:59' THEN '3月以上留存用户'
    ELSE '留存提问'
  END AS is_new_user,
  ss.`model`,
  ss.`uuid`,
  CASE
    WHEN LOWER(COALESCE(ss.model, '')) IN ('auto', 'pro', 'reason') THEN LOWER(ss.model)
    WHEN LOWER(COALESCE(ss.model, '')) IN ('qwen', 'qwen-plus', 'qwen3-max') THEN 'auto'
    WHEN LOWER(COALESCE(ss.model, '')) IN ('gemini-2.5-flash') THEN 'pro'
    WHEN LOWER(COALESCE(ss.model, '')) LIKE 'deepseek%' OR LOWER(COALESCE(ss.model, '')) IN
                                         ('deepseek', 'deepseek-r1', 'deepseek-r1-0528', 'deepseek-v3.2') THEN 'reason'
    WHEN LOWER(COALESCE(ss.model_type, '')) IN ('auto', 'pro', 'reason') THEN LOWER(ss.model_type)
    ELSE 'unset'
  END AS model_category,
  CASE
    WHEN bc.reaction_type = 1 THEN '赞'
    WHEN bc.reaction_type = 2 THEN '踩'
    ELSE ''
  END AS is_like
FROM
  `sigma-search`.`hot_session` ss
  LEFT JOIN `sigma-search`.`hot_search_record` sr ON ss.id = sr.session_id
  LEFT JOIN `sigma-search`.`hot_question` hq ON sr.id = hq.last_answer_id 
  LEFT JOIN `bohrium`.`common_like` bc ON bc.scene_id = sr.id AND bc.scene_type = 11
  INNER JOIN account_center.user u ON u.id = hq.user_id
WHERE
  ss.`create_time` >= '2025-12-01 00:00:00'
  AND ss.`create_time` < '2026-01-16 00:00:00'
  AND hq.`query` IS NOT NULL
