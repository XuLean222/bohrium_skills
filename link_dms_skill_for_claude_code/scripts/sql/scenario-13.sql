SELECT
    *
FROM
  user_questions_v
WHERE
  question <> ''
  and ask_time >= '2026-03-30 00:00:00'
  and ask_time < '2026-03-31 00:00:00'
  AND `user_id` != '14329'
  and `user_id` != '897445'
