"""
FastAPI application exposing network health metrics.

Endpoints
---------
- GET /                     -> HTML dashboard
- GET /health               -> Simple liveness check
- GET /interfaces/latest    -> Latest sample per interface
- GET /interfaces/summary   -> Per-interface KPIs (availability, error rate)
"""

from pathlib import Path
from typing import List

from fastapi import FastAPI, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine, Base
from app import models
from app.models import InterfaceSample
from app.schemas import InterfaceSampleOut, InterfaceSummaryOut
from app.config import settings  # noqa: F401  (imported so settings are loaded)


# ---------------------------------------------------------------------------
# Database bootstrap
# ---------------------------------------------------------------------------

# Make sure tables exist even if the collector has not been run yet.
Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# FastAPI app & static / template configuration
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Network SNMP Health API",
    version="0.1.0",
)

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static",
)


# ---------------------------------------------------------------------------
# Dependency: one DB session per request
# ---------------------------------------------------------------------------

def get_db() -> Session:
    """
    FastAPI dependency that provides a SQLAlchemy session.

    The session is created at the start of the request and closed at the end.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Render the main HTML dashboard.

    The frontend JavaScript then calls:

    - `GET /interfaces/latest`
    - `GET /interfaces/summary`

    to populate the table and the KPI cards.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
def health() -> dict:
    """Simple liveness endpoint used for health checks."""
    return {"status": "ok"}


@app.get("/interfaces/latest", response_model=List[InterfaceSampleOut])
def get_latest_samples(db: Session = Depends(get_db)):
    """
    Return the latest sample per interface (`if_index`).

    Implementation steps:
    1. Build a subquery that finds `max(ts)` per `if_index`.
    2. Join that subquery back to `InterfaceSample` to get the full rows.
    3. Order the result by `if_index` for a stable, readable output.
    """
    subq = (
        db.query(
            InterfaceSample.if_index,
            func.max(InterfaceSample.ts).label("max_ts"),
        )
        .group_by(InterfaceSample.if_index)
        .subquery()
    )

    q = (
        db.query(InterfaceSample)
        .join(
            subq,
            (InterfaceSample.if_index == subq.c.if_index)
            & (InterfaceSample.ts == subq.c.max_ts),
        )
        .order_by(InterfaceSample.if_index)
    )

    return q.all()


@app.get("/interfaces/summary", response_model=List[InterfaceSummaryOut])
def get_interface_summary(db: Session = Depends(get_db)):
    """
    Return high-level KPIs per interface.

    For each `if_index` we compute:

    - `sample_count`:
        How many samples we have in total.

    - `availability_percent`:
        Percentage of samples where `oper_status == 1` (interface is UP).

    - `error_rate_percent`:
        A simple "packet error rate" based on the change in octets vs errors
        between the *first* and *last* samples we have stored.

    This is intentionally simple but gives you realistic NOC-style metrics.
    """
    summaries: list[InterfaceSummaryOut] = []

    # 1) Get the list of interfaces we have ever seen.
    if_indexes = db.query(InterfaceSample.if_index).distinct().all()

    for (idx,) in if_indexes:
        # All samples for this interface
        q = db.query(InterfaceSample).filter(InterfaceSample.if_index == idx)

        sample_count = q.count()
        if sample_count == 0:
            continue

        # First & last samples in time (using the `ts` column from the model)
        first_sample = q.order_by(InterfaceSample.ts.asc()).first()
        last_sample = q.order_by(InterfaceSample.ts.desc()).first()

        # Number of samples where the interface was UP
        up_count = q.filter(InterfaceSample.oper_status == 1).count()

        availability = (
            (up_count / sample_count) * 100.0 if sample_count > 0 else 0.0
        )

        # Approximate error rate using deltas between first and last samples
        delta_in_octets = max(last_sample.in_octets - first_sample.in_octets, 0)
        delta_out_octets = max(last_sample.out_octets - first_sample.out_octets, 0)
        delta_errors = (
            max(last_sample.in_errors - first_sample.in_errors, 0)
            + max(last_sample.out_errors - first_sample.out_errors, 0)
        )

        total_traffic = delta_in_octets + delta_out_octets
        error_rate = (
            (delta_errors / total_traffic) * 100.0 if total_traffic > 0 else 0.0
        )

        summaries.append(
            InterfaceSummaryOut(
                if_index=idx,
                if_name=last_sample.if_name,
                sample_count=sample_count,
                availability_percent=availability,
                error_rate_percent=error_rate,
                first_sample_time=first_sample.ts,
                last_sample_time=last_sample.ts,
            )
        )

    return summaries
