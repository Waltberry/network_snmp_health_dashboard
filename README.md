# SNMP Network Health Dashboard

Small end-to-end **SNMP network health monitor** built with:

- 🐍 **Python** (3.11+)
- ⚡ **FastAPI** for the API + simple web UI
- 🗄️ **SQLite** (`metrics.db`) via SQLAlchemy
- 📡 **pysnmp** for SNMP polling (or an in-process stub)
- 🧪 Optional **SNMP simulator** (`snmpsim`) for local testing

It periodically polls one or more interfaces on a router / lab device / SNMP simulator, stores counters in SQLite, and exposes:

- `/interfaces/latest` – latest KPIs per interface
- `/interfaces/summary` – high-level availability & error-rate KPIs
- `/` – a small HTML “NOC-style” dashboard

---

## UI

![SNMP Network Health Dashboard UI](images/SNMP_network_network_health_dashboard.png)

The dashboard shows:

- **Interface Overview cards** – availability %, error rate %, sample window  
- **Latest Interface Metrics** table – admin/oper status, utilisation %, errors, last seen time, and health status (HEALTHY / WARN / CRITICAL).

The page auto-refreshes every 10 seconds.

---

## Features

- ✅ Poll SNMP counters (or use a local stub if you don’t have a device)
- ✅ Store metrics in **SQLite** (`metrics.db`) for easy inspection / export
- ✅ JSON APIs for latest samples and summary KPIs
- ✅ Simple HTML + CSS dashboard (no front-end framework required)
- ✅ Clean separation between **collector**, **SNMP client**, **API**, and **DB models**
- ✅ Ready to extend with **Grafana** or other visualisation tools

---

## Project Structure

```text
network-snmp-health-dashboard/
├── app/
│   ├── api.py           # FastAPI endpoints
│   ├── main.py          # ASGI entrypoint: `app = FastAPI(...)`
│   ├── collector.py     # SNMP polling loop -> writes to metrics.db
│   ├── config.py        # Pydantic Settings (env/.env based config)
│   ├── database.py      # SQLAlchemy engine + session
│   ├── models.py        # SQLAlchemy models (InterfaceSample)
│   ├── schemas.py       # Pydantic response models
│   ├── snmp_client.py   # Real SNMP client + stub implementation
│   ├── templates/
│   │   └── index.html   # Dashboard UI
│   └── static/
│       └── styles.css   # Basic styling
├── images/
│   └── SNMP_network_network_health_dashboard.png
├── .env                 # Local config (not committed)
├── metrics.db           # SQLite database (created at runtime)
└── requirements.txt
```

---

## Requirements

* Python **3.11+**
* (Optional) `snmpsim` for running a local SNMP simulator

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Configuration

Configuration is handled via Pydantic settings (`app/config.py`), reading from environment variables or `.env`.

Typical `.env` for local development:

```env
# Database URL (SQLite by default)
DB_URL=sqlite:///./metrics.db

# SNMP target
SNMP_HOST=127.0.0.1
SNMP_PORT=1161
SNMP_COMMUNITY=demo

# Polling behaviour
SNMP_IF_INDEXES=1         # comma-separated list, e.g. "1,2,3"
POLL_INTERVAL_SECONDS=10

# Mode: 1 = use stubbed SNMP, 0 = real SNMP (device or snmpsim)
USE_SNMP_STUB=1
```

### Two modes

1. **Stubbed SNMP (`USE_SNMP_STUB=1`)**

   * No real SNMP device required.
   * `app.snmp_client` generates deterministic, slowly-changing counters.
   * Good for running tests, demos, and screenshots.

2. **Real SNMP (`USE_SNMP_STUB=0`)**

   * Uses `pysnmp` to poll a real router / lab device or an SNMP simulator.
   * Controlled by `SNMP_HOST`, `SNMP_PORT`, `SNMP_COMMUNITY`, `SNMP_IF_INDEXES`.

---

## Running the Collector

The collector is a long-running process that polls SNMP and writes to `metrics.db`.

```bash
# Activate your virtualenv first
python -m app.collector
```

Example log output:

```text
[collector] Starting SNMP collector loop...
[collector] Polling interfaces: [1]
[collector] Poll interval: 10 seconds
[collector] Saved sample for ifIndex 1 at 2025-12-07 10:37:07.727716
...
```

You should see new rows appearing in `metrics.db` as it runs.

---

## Running the API & Dashboard

Start the FastAPI app with Uvicorn:

```bash
uvicorn app.main:app --reload
```

Then open:

* Dashboard: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
* Latest samples: [http://127.0.0.1:8000/interfaces/latest](http://127.0.0.1:8000/interfaces/latest)
* Summary KPIs: [http://127.0.0.1:8000/interfaces/summary](http://127.0.0.1:8000/interfaces/summary)

The dashboard uses plain JavaScript (`fetch`) to call `/interfaces/latest` and `/interfaces/summary` every 10 seconds and update the cards/table.

---

## Using an SNMP Simulator (snmpsim)

If you don’t have a lab router handy, you can use the `snmpsim` project.

1. Install:

   ```bash
   pip install snmpsim
   ```

2. Place a recording file (e.g. `demo.snmprec`) in the project root.
   `snmpsim` ships with examples – you can also capture your own walks.

3. Start the simulator in a separate terminal:

   ```bash
   snmpsim-command-responder --agent-udpv4-endpoint=127.0.0.1:1161 --data-dir=.
   ```

4. Update `.env`:

   ```env
   USE_SNMP_STUB=0
   SNMP_HOST=127.0.0.1
   SNMP_PORT=1161
   SNMP_COMMUNITY=demo
   ```

5. Restart the collector:

   ```bash
   python -m app.collector
   ```

Now the dashboard is driven by “real” SNMP responses from the simulator.

---

## API Overview

### `GET /health`

Simple liveness probe.

```json
{ "status": "ok" }
```

### `GET /interfaces/latest`

Returns the **latest sample per interface**.

Each item (shape simplified):

```json
{
  "if_index": 1,
  "if_name": "eth0",
  "admin_status": 1,
  "oper_status": 1,
  "in_util_percent": 3.42,
  "out_util_percent": 1.15,
  "in_errors": 0,
  "out_errors": 0,
  "sample_time": "2025-12-07T10:38:27.833307"
}
```

The frontend classifies each row as `HEALTHY` / `WARN` / `CRITICAL` based on utilisation, errors and oper status.

### `GET /interfaces/summary`

Returns **high-level KPIs per interface**:

* `sample_count` – number of rows we have for this `if_index`
* `availability_percent` – % of samples with `oper_status == 1`
* `error_rate_percent` – approximate packet error rate based on counter deltas
* `first_sample_time`, `last_sample_time` – time range of the data

Example:

```json
[
  {
    "if_index": 1,
    "if_name": "eth0",
    "sample_count": 120,
    "availability_percent": 100.0,
    "error_rate_percent": 0.02,
    "first_sample_time": "2025-12-07T10:37:07.727716",
    "last_sample_time": "2025-12-07T10:59:07.833307"
  }
]
```

These are what drive the “Interface Overview” cards at the top of the dashboard.

---

## Internals (Short Design Notes)

* **`app.snmp_client`**

  * `get_interface_snapshot(...)` hides SNMP details (real or stub).
  * Makes `getCmd` calls to IF-MIB OIDs (`ifDescr`, `ifInOctets`, `ifOutOctets`, `ifInErrors`, etc.) when `USE_SNMP_STUB=0`.
  * In stub mode, returns deterministic, synthetic counters to mimic traffic.

* **`app.collector`**

  * Reads config from `Settings` (Pydantic).
  * Polls each `if_index` every `POLL_INTERVAL_SECONDS`.
  * Stores samples as rows in the `interface_samples` table.

* **`app.models.InterfaceSample`**

  * SQLAlchemy model representing a single poll result.
  * Stores interface name, speed, counters, status flags, and timestamp.

* **`app.api` / `app.main`**

  * `/interfaces/latest` uses a subquery to get the latest timestamp per `if_index`.
  * `/interfaces/summary` computes availability and error-rate KPIs per interface.

* **`templates/index.html` + `static/styles.css`**

  * Minimal dashboard UI: cards + table.
  * Uses CSS classes (`healthy`, `warn`, `critical`) for intuitive colouring.

---

## Extending

Ideas for extending this project:

* 🔌 Add **Prometheus** metrics and scrape with a Prometheus server.
* 📊 Point **Grafana** at the SQLite DB (or a Prometheus exporter) for richer dashboards.
* 🚨 Implement alert rules (e.g. push notifications or email when utilisation or error rate crosses thresholds).
* 🧩 Add support for more MIBs and interface discovery.
