"""
SQLAlchemy ORM models.

Right now we only need a single table:

- InterfaceSample: one row per (timestamp, interface) snapshot
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, BigInteger, DateTime

from app.database import Base


class InterfaceSample(Base):
    """
    Represents one measurement snapshot for a network interface.

    Typical usage:
    - the collector polls SNMP
    - creates InterfaceSample objects
    - inserts them into the database
    """

    __tablename__ = "interface_samples"

    id = Column(Integer, primary_key=True, index=True)

    # When we took the measurement
    ts = Column(DateTime, index=True, default=datetime.utcnow, nullable=False)

    # Interface identity
    if_index = Column(Integer, index=True, nullable=False)
    if_name = Column(String(128), nullable=False)

    # Capacity
    if_speed_bps = Column(BigInteger, nullable=False)

    # Counters (simplified)
    in_octets = Column(BigInteger, nullable=False)
    out_octets = Column(BigInteger, nullable=False)
    in_errors = Column(BigInteger, nullable=False)
    out_errors = Column(BigInteger, nullable=False)

    # Admin and operational state from IF-MIB
    admin_status = Column(Integer, nullable=False)  # 1=up, 2=down, ...
    oper_status = Column(Integer, nullable=False)   # 1=up, 2=down, ...
