SELECT platform, COUNT(*) AS rows_cnt FROM (
SELECT hsr.meta->>'$.platform' AS platform
FROM hot_search_record hsr
    JOIN hot_session s ON s.id = hsr.session_id
WHERE COALESCE(s.meta->>'$.source','') <> 'openApi'
  AND hsr.create_time >= '2025-02-16 00:00:00'
  AND hsr.create_time < '2025-12-17 00:00:00'
UNION ALL
SELECT sr.meta->>'$.platform' AS platform
FROM search_record sr
    JOIN session s2 ON s2.id = sr.session_id
WHERE COALESCE(s2.meta->>'$.source','') <> 'openApi'
  AND sr.create_time >= '2025-02-16 00:00:00'
  AND sr.create_time < '2025-12-17 00:00:00' ) x GROUP BY platform  ORDER BY rows_cnt DESC;
