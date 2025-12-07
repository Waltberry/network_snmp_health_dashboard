"""
Configuration for the SNMP Network Health Dashboard.

We use pydantic-settings (Pydantic v2) to load settings from:
- environment variables
- a local `.env` file in the project root
"""

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings.

    Environment variables (with defaults):

    - SNMP_HOST:             IP/address of the SNMP device (default: 127.0.0.1)
    - SNMP_PORT:             UDP port for SNMP (default: 161)
    - SNMP_COMMUNITY:        SNMPv2c community string (default: "public")
    - SNMP_IF_INDEXES:       Comma-separated list of ifIndex values (e.g. "1,2")
    - POLL_INTERVAL_SECONDS: How often to poll (in seconds, default: 10)
    - DATABASE_URL:          SQLAlchemy URL, default SQLite file "metrics.db"
    - USE_SNMP_STUB:         "1" or "0" to toggle fake SNMP data (default: 1/True)
    """

    snmp_host: str = "127.0.0.1"
    snmp_port: int = 161
    snmp_community: str = "public"

    # Will be populated from SNMP_IF_INDEXES env; we’ll parse it below.
    snmp_if_indexes: List[int] = Field(default_factory=lambda: [1])

    poll_interval_seconds: int = 10

    database_url: str = "sqlite:///./metrics.db"

    use_snmp_stub: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # ignore unknown env vars like old ones
    )

    @field_validator("snmp_if_indexes", mode="before")
    @classmethod
    def parse_if_indexes(cls, v):
        """
        Allow SNMP_IF_INDEXES to be specified as:

        - "1"            -> [1]
        - "1,2,3"        -> [1, 2, 3]
        - 1              -> [1]
        - [1, 2, 3]      -> [1, 2, 3]

        Pydantic was complaining because it got a single int instead of a list.
        """
        if isinstance(v, list):
            return v
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            return [int(p) for p in parts]
        # fallback: just return as-is and let Pydantic complain if totally wrong
        return v


# Single global settings object
settings = Settings()
