SELECT
      ubr.*
  FROM
      `account_center`.`user_behavior_record` ubr
      INNER JOIN `sigma-search`.`hot_session`  hs
          ON hs.`uuid` = ubr.conversation_id COLLATE utf8mb4_general_ci
  WHERE
      ubr.`scene` = 'scholar_QA'
      AND ubr.`status` = 1
      AND ubr.`session_id` LIKE 'adk\_a\_%'
      AND `ubr`.`create_time` >= '2026-03-30 00:00:00'
      AND `ubr`.`create_time` < '2026-03-31 00:00:00'
