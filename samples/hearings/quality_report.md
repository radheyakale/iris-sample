# Hearings quality report

Counts are from the fixtures, not from a claim that the live listing currently contains these procedures.

Inputs: `tests/fixtures/hearings/listing.html`, `empty.html`, and `signals.json`. A live fetch of `/de/mitmachen` is stored under `data/raw/hearings/` and does not currently contain a substation-expansion hearing or a regional-plan amendment.

| Check | Count |
|---|---|
| Rows loaded (inserted + updated + unchanged) | 3 |
| Inserted on first load | 3 |
| Duplicates skipped | 1 |
| Empty pages | 1 |
| Ambiguous locations (place name, no coordinate) | 1 |
| Unresolved locations (non-numeric coordinate) | 1 |
| Resolved EPSG:25832 points | 1 |
| Records dropped for missing fields | 2 |
| Records dropped as not relevant | 1 |
| Malformed records | 1 |

The two missing-field drops are the HTML teaser with a link and no headline, and the JSON record whose title is blank. The duplicate is the second copy of `regionalplanung-stuttgart`. The malformed record is the JSON value `"not-a-record"`. A JSON file that is not a list is reported as `malformed_file` and loads nothing.

A second load of the same source id inserts nothing. Validation queries are in `validation.sql`.
