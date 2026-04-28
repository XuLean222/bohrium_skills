SELECT month, COUNT(*) AS cnt
FROM (
SELECT DATE_FORMAT(hsr.create_time, '%Y-%m') AS month
FROM hot_search_record hsr
WHERE hsr.create_time >= '2025-12-14 00:00:00' AND hsr.create_time < '2025-12-16 00:00:00' AND hsr.meta->>'$.platform' = 'web'
  AND EXISTS (
  SELECT 1
  FROM hot_session s
  WHERE s.id = hsr.session_id AND
        COALESCE(s.meta->>'$.source','') <> 'openApi' )
UNION ALL
SELECT DATE_FORMAT(sr.create_time, '%Y-%m') AS month
FROM search_record sr
WHERE sr.create_time >= '2025-12-14 00:00:00' AND sr.create_time < '2025-12-16 00:00:00'
  AND sr.meta->>'$.platform' = 'web'
  AND EXISTS (
  SELECT 1
  FROM session s2
  WHERE s2.id = sr.session_id
    AND COALESCE(s2.meta->>'$.source','') <> 'openApi' ) ) t
GROUP BY month ORDER BY month;
