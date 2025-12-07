"""
Background collector process.

This module:
- connects to the SNMP client (stub or real)
- collects metrics for each configured interface
- writes InterfaceSample rows into the database

Run it as:

    $env:USE_SNMP_STUB="1"
    python -m app.collector

or (for real SNMP, once pysnmp/device works):

    $env:USE_SNMP_STUB="0"
    python -m app.collector
"""

import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, SessionLocal, Base
from app.models import InterfaceSample
from app.snmp_client import get_interface_snapshot, SnmpError


# Create DB tables on startup (no-op if they already exist)
Base.metadata.create_all(bind=engine)


def poll_once(db: Session) -> None:
    """
    Poll all configured interfaces once and insert samples into the DB.
    """
    for if_idx in settings.snmp_if_indexes:
        try:
            snap = get_interface_snapshot(
                host=settings.snmp_host,
                community=settings.snmp_community,
                port=settings.snmp_port,
                if_index=if_idx,
            )
        except SnmpError as exc:
            print(f"[collector] SNMP error for ifIndex {if_idx}: {exc}")
            continue

        sample = InterfaceSample(
            ts=datetime.utcnow(),
            if_index=snap["if_index"],
            if_name=snap["if_name"],
            if_speed_bps=snap["if_speed_bps"],
            in_octets=snap["in_octets"],
            out_octets=snap["out_octets"],
            in_errors=snap["in_errors"],
            out_errors=snap["out_errors"],
            admin_status=snap["admin_status"],
            oper_status=snap["oper_status"],
        )
        db.add(sample)
        print(f"[collector] Saved sample for ifIndex {if_idx} at {sample.ts}")


def main() -> None:
    """
    Main collector loop: open a DB session, poll, commit, sleep, repeat.
    """
    print("[collector] Starting SNMP collector loop...")
    print(f"[collector] Polling interfaces: {settings.snmp_if_indexes}")
    print(f"[collector] Poll interval: {settings.poll_interval_seconds} seconds")

    while True:
        with SessionLocal() as db:
            poll_once(db)
            db.commit()
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
