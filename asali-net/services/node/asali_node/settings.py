"""Everything a node needs to know about itself, read from the environment (TASKS.md 2.2)."""

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings

OrgType = Literal["pharma", "distributor", "shop", "consumer", "regulator"]
Engine = Literal["postgres", "mongo", "sqlite"]


class Settings(BaseSettings):
    # identity
    org_id: str
    org_type: OrgType
    org_name: str
    org_city: str
    org_state: str
    issuer_code: str | None = None
    gs1_prefix: str | None = None
    # own storage
    engine: Engine
    db_rw_url: str | None = None
    db_ro_url: str | None = None
    sqlite_path: Path | None = None
    meili_url: str | None = None
    meili_master_key: str | None = None
    # network
    directory_url: str
    join_token: str
    public_base_url: str
    host_name: str
    # mode and local data
    asali_mode: Literal["network", "simulation"] = "network"
    data_dir: Path = Path("/data")
    shop_settings_json: str | None = None
    staff_seed_json: str | None = None
    served_states: str | None = None  # JSON list of state codes a distributor serves

    @field_validator("shop_settings_json")
    @classmethod
    def _json_object(cls, v: str | None) -> str | None:
        if v is not None and not isinstance(json.loads(v), dict):
            raise ValueError("SHOP_SETTINGS_JSON must be a JSON object")
        return v

    @property
    def shop_settings(self) -> dict[str, Any] | None:
        return json.loads(self.shop_settings_json) if self.shop_settings_json else None
