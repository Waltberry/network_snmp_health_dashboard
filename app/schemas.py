"""
Pydantic models ("schemas") for API responses.

We keep these separate from the ORM models so the API layer
does not expose SQLAlchemy internals.
"""

from datetime import datetime

from pydantic import BaseModel


class InterfaceSampleOut(BaseModel):
    """
    Full view of an InterfaceSample row for API responses.
    """

    id: int
    ts: datetime
    if_index: int
    if_name: str
    if_speed_bps: int
    in_octets: int
    out_octets: int
    in_errors: int
    out_errors: int
    admin_status: int
    oper_status: int

    class Config:
        from_attributes = True  # allows .from_orm(...) in Pydantic v2


class InterfaceSummaryOut(BaseModel):
    """
    Per-interface KPIs used by /interfaces/summary.

    - sample_count: number of rows we have for this ifIndex
    - availability_percent: % of samples with oper_status == 1 (UP)
    - error_rate_percent: approximate packet error rate using first/last counters
    - first_sample_time / last_sample_time: time window of the data used
    """
    if_index: int
    if_name: str
    sample_count: int
    availability_percent: float
    error_rate_percent: float
    first_sample_time: datetime
    last_sample_time: datetime