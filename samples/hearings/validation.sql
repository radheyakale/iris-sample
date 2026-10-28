-- Staging checks for iris_staging.signal_ingest.
-- The migration creates this schema. Do not create a schema named app for this table.

-- Signal types and location outcomes.
SELECT
    signal_type,
    location_status,
    count(*) AS rows
FROM iris_staging.signal_ingest
GROUP BY signal_type, location_status
ORDER BY signal_type, location_status;

-- A re-run must not create a second row for the same source.
SELECT
    source_system,
    source_id,
    count(*) AS rows
FROM iris_staging.signal_ingest
GROUP BY source_system, source_id
HAVING count(*) > 1;

-- Resolved rows have a point. Every other status has a null geometry.
SELECT
    id,
    source_id,
    location_status
FROM iris_staging.signal_ingest
WHERE (
    location_status = 'resolved'
    AND geom IS NULL
)
OR (
    location_status <> 'resolved'
    AND geom IS NOT NULL
);

-- Trace a row back to the public page, including unresolved coordinates.
SELECT
    source_id,
    signal_type,
    title,
    published_at,
    participation_start,
    participation_end,
    source_url,
    place_text,
    location_status,
    location_note,
    ST_AsText(geom) AS geom_25832
FROM iris_staging.signal_ingest
ORDER BY signal_type, source_id;
