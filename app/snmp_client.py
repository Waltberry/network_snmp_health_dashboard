"""
SNMP client abstraction.

We support two modes:

1. Real SNMP (using pysnmp), if available and USE_SNMP_STUB=0.
2. Stub mode: generate realistic-looking counters in-memory.

This lets you:
- run everything locally without a real router
- later flip a flag and talk to a real SNMP device
"""

from __future__ import annotations

import os
import random
import time
from typing import Dict, Any

from app.config import settings


class SnmpError(Exception):
    """Raised when SNMP retrieval fails."""


# Try importing pysnmp, but don't hard-fail if it's missing or broken
try:
    from pysnmp.hlapi import (
        SnmpEngine,
        CommunityData,
        UdpTransportTarget,
        ContextData,
        ObjectType,
        ObjectIdentity,
        getCmd,
    )

    HAS_PYSNMP = True
except Exception:  # ImportError, etc.
    HAS_PYSNMP = False


# ---------------------------------------------------------------------------
# Stub implementation: fake counters for demo purposes
# ---------------------------------------------------------------------------

# Per-interface in-memory state for stub mode
_stub_state: Dict[int, Dict[str, int]] = {}


def _init_stub_interface(if_index: int) -> None:
    """Initialize fake counters for a given interface index."""
    if if_index in _stub_state:
        return

    # Seed counters with some baseline values
    _stub_state[if_index] = {
        "if_speed_bps": 100_000_000,  # 100 Mbps
        "in_octets": random.randint(1_000_000, 10_000_000),
        "out_octets": random.randint(1_000_000, 10_000_000),
        "in_errors": 0,
        "out_errors": 0,
        "admin_status": 1,  # up
        "oper_status": 1,   # up
    }


def _stub_get_interface_snapshot(if_index: int) -> Dict[str, Any]:
    """
    Generate a fake interface snapshot.

    Each call increments counters by a random amount to simulate traffic.
    """
    _init_stub_interface(if_index)
    st = _stub_state[if_index]

    # Simulate traffic increments
    delta_in = random.randint(10_000, 100_000)
    delta_out = random.randint(10_000, 100_000)
    st["in_octets"] += delta_in
    st["out_octets"] += delta_out

    # Occasionally introduce a small error
    if random.random() < 0.01:
        st["in_errors"] += random.randint(1, 10)
    if random.random() < 0.01:
        st["out_errors"] += random.randint(1, 10)

    return {
        "if_index": if_index,
        "if_name": f"stub-if{if_index}",
        "if_speed_bps": st["if_speed_bps"],
        "in_octets": st["in_octets"],
        "out_octets": st["out_octets"],
        "in_errors": st["in_errors"],
        "out_errors": st["out_errors"],
        "admin_status": st["admin_status"],
        "oper_status": st["oper_status"],
    }


# ---------------------------------------------------------------------------
# Real SNMP implementation (if pysnmp works)
# ---------------------------------------------------------------------------


def _snmp_get_int(
    host: str,
    community: str,
    port: int,
    oid: str,
) -> int:
    """
    Perform an SNMPv2c GET for a single OID and return its integer value.
    """
    iterator = getCmd(
        SnmpEngine(),
        CommunityData(community, mpModel=1),  # SNMP v2c
        UdpTransportTarget((host, port), timeout=1, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )

    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)

    if errorIndication:
        raise SnmpError(str(errorIndication))
    if errorStatus:
        msg = f"{errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
        raise SnmpError(msg)

    for _, value in varBinds:
        return int(value)

    raise SnmpError("No varBinds returned")


def _snmp_get_interface_snapshot(
    host: str,
    community: str,
    port: int,
    if_index: int,
) -> Dict[str, Any]:
    """
    Retrieve counters for an interface via IF-MIB.

    OIDs used (1.3.6.1.2.1.2.2.1.X.ifIndex):
    - ifDescr       (2)
    - ifSpeed       (5)
    - ifAdminStatus (7)
    - ifOperStatus  (8)
    - ifInOctets    (10)
    - ifInErrors    (14)
    - ifOutOctets   (16)
    - ifOutErrors   (20)
    """
    base = "1.3.6.1.2.1.2.2.1"

    # ifDescr (string) needs special handling
    iterator = getCmd(
        SnmpEngine(),
        CommunityData(community, mpModel=1),
        UdpTransportTarget((host, port), timeout=1, retries=1),
        ContextData(),
        ObjectType(ObjectIdentity(f"{base}.2.{if_index}")),
    )
    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
    if errorIndication:
        raise SnmpError(str(errorIndication))
    if errorStatus:
        msg = f"{errorStatus.prettyPrint()} at {errorIndex and varBinds[int(errorIndex) - 1][0] or '?'}"
        raise SnmpError(msg)
    if_name = str(varBinds[0][1])

    # Numeric fields
    if_speed = _snmp_get_int(host, community, port, f"{base}.5.{if_index}")
    admin_status = _snmp_get_int(host, community, port, f"{base}.7.{if_index}")
    oper_status = _snmp_get_int(host, community, port, f"{base}.8.{if_index}")
    in_octets = _snmp_get_int(host, community, port, f"{base}.10.{if_index}")
    in_errors = _snmp_get_int(host, community, port, f"{base}.14.{if_index}")
    out_octets = _snmp_get_int(host, community, port, f"{base}.16.{if_index}")
    out_errors = _snmp_get_int(host, community, port, f"{base}.20.{if_index}")

    return {
        "if_index": if_index,
        "if_name": if_name,
        "if_speed_bps": if_speed,
        "in_octets": in_octets,
        "out_octets": out_octets,
        "in_errors": in_errors,
        "out_errors": out_errors,
        "admin_status": admin_status,
        "oper_status": oper_status,
    }


# ---------------------------------------------------------------------------
# Public API function used by the collector
# ---------------------------------------------------------------------------


def get_interface_snapshot(
    host: str,
    community: str,
    port: int,
    if_index: int,
) -> Dict[str, Any]:
    """
    Main entry point: returns a snapshot for an interface.

    Decision logic:
    - If USE_SNMP_STUB env var or settings.use_snmp_stub is true, use stub.
    - Else, if pysnmp is available, perform real SNMP.
    - Else, fall back to stub with a warning.
    """
    # Shell env overrides settings.use_snmp_stub if present
    use_stub_env = os.getenv("USE_SNMP_STUB")
    if use_stub_env is not None:
        use_stub = use_stub_env not in ("0", "false", "False")
    else:
        use_stub = settings.use_snmp_stub

    if use_stub:
        return _stub_get_interface_snapshot(if_index)

    if not HAS_PYSNMP:
        # Fallback: no pysnmp, but stub still allows the rest of the stack to work
        print("[snmp_client] pysnmp not available, falling back to stub mode.")
        return _stub_get_interface_snapshot(if_index)

    # Real SNMP path
    return _snmp_get_interface_snapshot(host, community, port, if_index)
