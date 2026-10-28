# Baden-Württemberg hearings ingest

Public hearings for substation expansions and regional plan amendments, loaded into `iris_staging.signal_ingest`.

The table lives in `iris_staging`. The Alembic migration creates that schema. It is not an `app` schema.

Tested on PostgreSQL 16 and PostGIS 3.4. `docker-compose.yml` uses `postgis/postgis:16-3.4`. `platform: linux/amd64` was added because this was tested on a MacBook. A data volume created by PostgreSQL 17 will not start under this image. Recreate that volume before `alembic upgrade head`.

## Source

| | |
|---|---|
| Portal | https://beteiligungsportal.baden-wuerttemberg.de |
| Listing used | https://beteiligungsportal.baden-wuerttemberg.de/de/mitmachen |
| Pattern | HTML. Selectors are `article.teaser` and, where present, `li.link-list__item`. |
| Source system stored on each row | `beteiligung_bw` |

`/de/mitmachen` is the public participation listing: procedure teasers and recent comments. The portal home page is configured as a second URL and is not fetched.

## Why the search page is excluded

`/de/system/suchergebnisseite` can search announcements, and it is the page that paginates. `robots.txt` disallows it for `User-agent: *`. The scraper reads `https://beteiligungsportal.baden-wuerttemberg.de/de/robots.txt` through the shared HTTP client and does not request a disallowed URL.

`/de/mitmachen` is allowed. It is one HTML document. `page` and `pageSize` do not change it, so the scraper fetches that listing once and deletes any older `page_*.html` files from a previous five-page run. A second load does not insert rows whose `(source_system, source_id)` and content hash are already stored.

## Field mapping

| Staging column | Source |
|---|---|
| `source_id` | `comment[searchComment]` when the URL has one, otherwise the last path segment |
| `title` | `.teaser__headline` (`h2` or `h3`) |
| `published_at` | A date introduced as Veröffentlichung, Bekanntmachung, or publiziert. A deadline is not treated as the publication date. |
| `participation_start` | Date after vom / von / ab |
| `participation_end` | Date after bis / bis zum |
| `source_url` | Teaser link, resolved against the page base href |
| `place_text` | Place captured from "in {Place}" or "Haushalt {Place}" |
| `signal_type` | `regional_plan_amendment` or `substation_expansion_hearing`, from the title and place text |
| `geom` | EPSG:25832 point when the record has a usable longitude/latitude or easting/northing |
| `location_status` | `resolved`, `ambiguous` (place only), or `unresolved` |
| `location_note` | Why a point was not stored |
| `raw_payload` | The parsed record |
| `content_hash` | Hash of the staged fields, used to skip an unchanged re-run |

Dates that are not a real calendar day stay null. A teaser with no title or no link is counted and dropped. The live listing's procedure cards say "bis zum {date}", which is stored as `participation_end`.

A place name without a coordinate is `ambiguous`. A missing location, a non-numeric value, `(0, 0)`, an unknown CRS, or a point outside the Germany bounds is `unresolved` and the geometry stays null. Longitude/latitude in EPSG:4326 is transformed to EPSG:25832. Values already in EPSG:25832 are stored after the same bounds check.

## Assumptions

- Hearings belong in phase 1 because they are part of data acquisition. `python main.py all` runs the scraper and then the loader there.
- `/de/mitmachen` is the listing to fetch. The portal home page is configured and is not fetched. `/de/system/suchergebnisseite` is not used because `robots.txt` disallows it.
- A row is kept only when the title or place text is a hearing and either regional planning or a substation expansion. Other procedures on the same page are counted and dropped.

## How to run

```bash
cp .env.example .env
docker compose up -d postgres
docker exec -it nrw-postgis psql -U postgres -d nrw_dc_bi -c "CREATE EXTENSION IF NOT EXISTS postgis;"
alembic upgrade head

python main.py hearings
python main.py hearings-load
```

`python main.py hearings` fetches the listing and writes `data/raw/hearings/page_1.html`, `merged.json`, and `parse_quality.json`.

`python main.py hearings-load` upserts relevant rows and writes `data/raw/hearings/quality_report.json`.

Tests that do not need a database:

```bash
python -m unittest tests.test_hearings_html tests.test_hearings_scraper tests.test_hearings_filter tests.test_hearings_robots tests.test_signal_ingest
```

Database ingest, after `alembic upgrade head`. This loads `tests/fixtures/hearings/signals.json` into `iris_staging.signal_ingest`, checks both signal types, the EPSG:25832 point, the rejected coordinate, and a second load that inserts nothing, then rolls the transaction back:

```bash
python -m unittest tests.test_signal_ingest_db
```

The database test skips when `DATABASE_URL` is unset or `iris_staging.signal_ingest` is missing. It expects PostgreSQL 16 and PostGIS 3.4.

## How I tested the ingest manually

The live `/de/mitmachen` listing currently has no relevant hearing, so `hearings-load` inserts nothing. To leave the fixture rows in `iris_staging.signal_ingest`:

```bash
cp tests/fixtures/hearings/signals.json data/raw/hearings/merged.json
python main.py hearings-load
```

This replaces `data/raw/hearings/merged.json` with the fixture and upserts the three kept rows. The database test above rolls its transaction back and does not leave those rows.

## Sample output

| File | What it is |
|---|---|
| `tests/fixtures/hearings/listing.html` | Public-style teasers for both signal types, one irrelevant teaser, one teaser with no title |
| `tests/fixtures/hearings/empty.html` | Empty page |
| `tests/fixtures/hearings/signals.json` | Loader input, including a coordinate, a duplicate, a blank title, and a non-numeric coordinate |
| `samples/hearings/signal_ingest_sample.json` | The three rows the loader keeps |
| `samples/hearings/quality_report.md` | Counts for that fixture run |
| `samples/hearings/validation.sql` | Queries for signal type, duplicates, and geometry status |

`python main.py hearings` writes the live `/de/mitmachen` page to `data/raw/hearings/`. That directory is gitignored. The listing does not currently contain either target signal, so the load inserts nothing. `samples/hearings/` is the committed fixture output for the rows the allowed page cannot provide.

## Limitations

- The HTML selectors and the place-name patterns are specific to this portal. A layout change needs a parser change. `HearingsHTMLDataParser` exists for that reason.
- Relevance is a regex over the title and place text: a hearing, plus either regional planning or an Umspannwerk / Schaltanlage together with Erweiterung, Ersatzneubau, Neubau, or Ausbau. Other procedures on the same page are counted and dropped.
- The allowed page does not publish coordinates, so live rows from `/de/mitmachen` stay `ambiguous` or `unresolved`. The resolved sample point comes from the fixture.
- Search pagination stays unused because `robots.txt` disallows it.
- Network timeouts, connection errors, HTTP 429, and HTTP 500/502/503/504 are retried by `HttpClient`. A failure after those retries stops the scrape. An empty body is saved and counted.
- Invalid JSON does not load. It is reported as `malformed_file`.

## Disclaimer

I used Cursor AI for about 30–40% of the code. That includes extracting tags with BeautifulSoup, writing the HTML fixtures and JSON so both relevant and irrelevant articles are covered, and the GeoAlchemy code in `signal_ingest_loader.py`.
