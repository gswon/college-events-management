# NYU Events Ingest (Data Team)

> This is the `data/` folder of the team repo, next to `frontend/` and `backend/`.
> Run every command below from inside `data/`.

Collects events from four NYU sources and loads them into the MySQL `events` table
(plus `organizations`). The database schema is the backend's shared `NYUEventSchema.sql`.

| `--source` | `events.source` | Where it comes from | Format | `external_id` |
|---|---|---|---|---|
| `nyu_events` | `NYU_EVENTS` | events.nyu.edu LiveWhale JSON API | JSON | LiveWhale id / `engage-<id>` / recurring: `<id>@<start timestamp>` |
| `wasserman` | `WASSERMAN` | wasserman.nyu.edu RSS → per-event `.ics` | RSS + iCal | Handshake event ID |
| `athletics` | `ATHLETICS` | gonyuathletics.com all-sports iCal | iCal | Sidearm game ID |
| `academic` | `ACADEMIC` | bulletins.nyu.edu academic calendar table | HTML | hash of (term + date + text) |

## Files

| File | Purpose |
|---|---|
| `NYUEventSchema.sql` | App schema (12 tables + 7 categories). **Verbatim copy of `backend/NYUEventSchema.sql` — do not edit here.** |
| `schema_ingest.sql` | Ingest-only tables: `raw_events`, `ingest_runs` |
| `ingest/` | The collector (`python -m ingest.run`) |
| `ingest/migrate.py` | Applies the schema files (see "Schema" below) |
| `Dockerfile`, `railway.json` | Railway cron deployment |
| `tests/` | Tests (fixtures = saved responses from the real sites) |

## Pipeline

```
1. fetch()         download from the site                     ingest/sources/<source>.py
2. save_raw()      store the raw payload in raw_events         ingest/store.py  (stops here if the hash is unchanged)
3. normalize()     convert to the common Event shape           ingest/sources/<source>.py
4. upsert_event()  upsert into events (+ organizations)        ingest/store.py  (key: source + external_id)
finally            refresh last_synced_at for events still in the feed,
                   mark future events that disappeared as CANCELLED, log the run in ingest_runs
```

## How the `events` columns are filled

| Column | Rule |
|---|---|
| `source`, `external_id` | See the table above. Together they are the upsert key |
| `source_url` | Original event page (NULL if longer than 500 chars) |
| `title`, `description` | HTML tags/entities removed. Prefixes like `CANCELED:` are stripped and reflected in `status` |
| `category_id` | Category code → `event_categories.id` (rules below) |
| `organization_id` | Wasserman → `wasserman`, Athletics → `nyu-athletics`, events.nyu.edu → department group (`gid-<n>`). NULL for Engage clubs and the academic calendar |
| `host_name` | Organizer name as written in the source |
| `start_at`, `end_at` | UTC. If there is no end time: `start_at + 1 hour` |
| `is_all_day` | `start_at` = first day at **midnight New York time** (in UTC), `end_at` = midnight of the **day after** the last day (exclusive) |
| `location_name`, `address` | Wasserman: split at the street number. Athletics: `City, ST` goes to `address` |
| `is_online`, `online_url` | LiveWhale `is_online` / `online_url`; Wasserman: location mentions Virtual/Zoom/etc. |
| `registration_url` | Handshake link |
| `image_url` | LiveWhale `thumbnail` |
| `is_free`, `price_text` | LiveWhale `cost` and the `Free` event type. NULL when unknown |
| `audience_text` | LiveWhale event types such as Students / Open to the Public |
| `status` | `ACTIVE` / `CANCELLED`. **Events an admin set to `HIDDEN` are never changed by the collector** |
| `last_synced_at` | Updated whenever the event is seen in the feed (`updated_at` only changes when the content changes) |

Category rules for events.nyu.edu (first match wins):
Engage club → `SOCIAL`, career/job/internship/… → `CAREER`, arts/music/film/… → `ARTS`,
wellness/health/mindfulness/… → `WELLNESS`, athletics/sports → `SPORTS`, lecture/research/seminar/deadlines/… → `ACADEMIC`, otherwise `OTHER`.
Wasserman is always `CAREER`, Athletics `SPORTS`, academic calendar `ACADEMIC`.

Events are never deleted, so users' saved events (`event_saves`) are preserved.

## Schema

`python -m ingest.migrate` (or `python -m ingest.run --migrate`) does the following:

- `NYUEventSchema.sql`: skips the `CREATE DATABASE` / `USE` lines (same as the backend's `scripts/apply_schema.py`)
  and applies the file **only if the `events` table does not exist yet**.
- `schema_ingest.sql`: `CREATE TABLE IF NOT EXISTS`, safe to run every time.

`INGEST_APPLY_SCHEMA` controls this: `all` (default), `ingest` (only the ingest tables — use this once the backend
manages the app tables), `none`.

When the backend changes `NYUEventSchema.sql`, copy it here again and run `python -m pytest tests/test_schema.py`.

## Running locally

```bash
# 1) Start MySQL (NYUEventSchema.sql and schema_ingest.sql are applied automatically into `nyu_calendar`)
docker compose up -d

# 2) Python packages (Python 3.11+)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 3) Connection settings
cp .env.example .env        # works as-is with docker-compose

# 4) Preview without touching the DB (makes real requests to the sites)
python -m ingest.run --source athletics --dry-run --limit 5

# 5) Save
python -m ingest.run                          # default sources: nyu_events, wasserman, athletics
python -m ingest.run --source academic        # academic calendar: check with --dry-run first, then run manually
python -m ingest.run --source all             # all four
```

Useful queries:

```sql
SELECT e.source, c.code, e.status, COUNT(*)
  FROM events e JOIN event_categories c ON c.id = e.category_id GROUP BY 1, 2, 3;
SELECT * FROM ingest_runs ORDER BY id DESC LIMIT 10;
```

## Deploying to Railway

The collector is a **cron job, not a web server**. Railway starts the container on a schedule,
runs `python -m ingest.run --migrate` once, and the container exits.

1. Add a **MySQL** service to the Railway project (MySQL 8.0.19+).
2. Add a service from this **GitHub repo**.
   - Settings → **Root Directory**: `/data`
   - Because of `railway.json`, it builds from the Dockerfile and the cron schedule (`0 */4 * * *` = every 4 hours, **UTC**) is set automatically.
3. Add these **Variables** to the collector service:

   | Variable | Value |
   |---|---|
   | `MYSQL_URL` | `${{MySQL.MYSQL_URL}}` (Railway reference variable, private network) |
   | `INGEST_APPLY_SCHEMA` | `all` at first → `ingest` once the backend creates the app tables |
   | `INGEST_SOURCES` | (optional) default `nyu_events,wasserman,athletics` |

4. Deploy. After the first run, check: `SELECT * FROM ingest_runs ORDER BY id DESC LIMIT 10;`

To run something manually (e.g. the academic calendar) against the Railway DB from your machine, use the
**public** URL (`*.railway.internal` only works inside Railway):

```bash
# copy MYSQL_PUBLIC_URL from the MySQL service's Variables
DATABASE_URL='mysql://root:...@xxx.proxy.rlwy.net:12345/railway' python -m ingest.run --source academic --dry-run --limit 40
DATABASE_URL='mysql://root:...@xxx.proxy.rlwy.net:12345/railway' python -m ingest.run --source academic
```

DB settings are read in this order: `DATABASE_URL` → `MYSQL_URL` → `MYSQLHOST`/`MYSQLUSER`/… → `DB_HOST`/`DB_USER`/… (`.env`).

To change the schedule, edit `cronSchedule` in `railway.json` or the service's Cron Schedule setting.
Railway skips a run if the previous one is still running. If any source fails, the process exits with code 1
and Railway shows the run as failed.

## After changing conversion logic

Unchanged raw payloads skip steps 3–4, so run once with `--force` after editing a `normalize()`:

```bash
python -m ingest.run --source nyu_events --force
```

## Tests

```bash
python -m pytest     # schema checks + per-source fetch/normalize (no network, no DB; uses tests/fixtures)

# Integration tests against real MySQL (DROPS all tables in the given DB — use a dedicated test DB)
docker compose exec mysql mysql -uroot -proot-change-me -e "CREATE DATABASE IF NOT EXISTS nyu_events_test"
TEST_DB_NAME=nyu_events_test TEST_DB_USER=root TEST_DB_PASSWORD=root-change-me python -m pytest
```

- `tests/test_schema.py` — `NYUEventSchema.sql` has the 12 spec tables and the exact `events` columns (type, NOT NULL), and every column the collector writes exists
- `tests/test_sources.py` — fetch + normalize for each source
- `tests/test_mysql_integration.py` — apply schema → load all sources → re-run, cancel, restore, keep `HIDDEN`, cascade on user delete

## Known limitations / next steps

- **To agree with the backend:** all-day `end_at` convention (next-day midnight, exclusive); source code for Engage events
  (spec example says `ENGAGE`, we currently use `NYU_EVENTS` with `engage-<id>` because they come from events.nyu.edu);
  who applies `NYUEventSchema.sql` on the shared Railway DB.
- **Wasserman is not auto-cancelled:** the RSS feed is paginated, so a missing event does not mean it was removed.
- **Duplicates across departments:** Wasserman (gid 109) and NYU Athletics groups are excluded from `nyu_events`,
  but the same event re-posted by another department (or academic-calendar entries posted by schools) can still appear twice.
- **Tags** are not stored (not in the spec); they are visible in `--dry-run` output and in `raw_events`.
- Requires **MySQL 8.0.19+** (`INSERT ... AS new ON DUPLICATE KEY UPDATE`).
