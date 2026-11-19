"""Load and check infra/network.yaml."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

CROCKFORD = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
NETWORK_YAML = Path(__file__).resolve().parents[1] / "network.yaml"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ShopInfo(Strict):
    area: str
    state_code: str
    receipt_language: Literal["en", "hi", "mr", "kn"]
    drug_licence_no: str
    gstin: str
    helpline: str


class Org(Strict):
    type: Literal["pharma", "distributor", "shop", "consumer", "regulator"]
    name: str
    city: str
    state: str
    engine: Literal["postgres", "mongo", "sqlite"]
    port: int
    pc: str
    issuer_code: str | None = None
    gs1_prefix: str | None = None
    served_states: list[str] = []
    shop: ShopInfo | None = None


class Pc(Strict):
    role: str
    machine: str


class DirectoryInfo(Strict):
    pc: str
    port: int


class Network(Strict):
    pcs: dict[str, Pc]
    directory: DirectoryInfo
    orgs: dict[str, Org]

    @model_validator(mode="after")
    def _consistent(self) -> "Network":
        ports = [self.directory.port, *(o.port for o in self.orgs.values())]
        if len(set(ports)) != len(ports):
            raise ValueError("two services share a port")
        for org_id, o in self.orgs.items():
            if o.pc not in self.pcs:
                raise ValueError(f"{org_id} is on unknown PC {o.pc}")
            if o.type == "pharma" and not (o.issuer_code and o.gs1_prefix):
                raise ValueError(f"{org_id} needs an issuer code and a GS1 prefix")
            if o.type == "shop" and o.shop is None:
                raise ValueError(f"{org_id} needs location settings")
            if o.type == "distributor" and not o.served_states:
                raise ValueError(f"{org_id} needs served states")
        codes = [o.issuer_code for o in self.orgs.values() if o.issuer_code]
        if len(set(codes)) != len(codes):
            raise ValueError("issuer codes must be unique")
        for c in codes:
            if len(c) != 2 or not set(c) <= CROCKFORD:
                raise ValueError(f"issuer code {c} must be 2 characters of the code alphabet")
        return self

    def on_pc(self, pc: str) -> dict[str, Org]:
        return {k: v for k, v in self.orgs.items() if v.pc == pc}


def load(path: Path = NETWORK_YAML) -> Network:
    return Network.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
