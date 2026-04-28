SELECT day, COUNT(*) AS cnt
FROM (
   SELECT DATE(s.create_time) AS day
FROM hot_session s
WHERE s.create_time >= '2025-12-01 00:00:00' AND s.create_time < '2025-12-16 00:00:00'
  AND COALESCE(s.meta->>'$.source','') <> 'openApi'
  AND EXISTS (
  SELECT 1
  FROM hot_search_record hsr
  WHERE hsr.session_id = s.id
    AND hsr.meta->>'$.platform' = 'web' )
UNION ALL
SELECT DATE(s.create_time) AS day
  FROM session s
  WHERE s.create_time >= '2025-12-01 00:00:00'
    AND s.create_time < '2025-12-16 00:00:00'
    AND COALESCE(s.meta->>'$.source','') <> 'openApi'
    AND EXISTS (
    SELECT 1
    FROM search_record sr
    WHERE sr.session_id = s.id AND sr.meta->>'$.platform' = 'web' ) ) t
GROUP BY day ORDER BY day;
