"""Which store class serves which organisation, on which engine."""

import importlib
from dataclasses import dataclass
from typing import Literal

Kind = Literal["pharma", "distributor", "shop", "consumer", "regulator"]
Engine = Literal["sqlite", "pg", "mongo"]


@dataclass(frozen=True)
class OrgStore:
    org_id: str
    kind: Kind
    engine: Engine
    module: str
    cls: str


ORG_STORES: dict[str, OrgStore] = {
    o.org_id: o
    for o in [
        OrgStore("tarang", "pharma", "pg", "tarang", "TarangStore"),
        OrgStore("medivra", "pharma", "mongo", "medivra", "MedivraStore"),
        OrgStore("kesar", "pharma", "sqlite", "kesar", "KesarStore"),
        OrgStore("dist-north", "distributor", "pg", "dist_north", "DistNorthStore"),
        OrgStore("dist-west", "distributor", "mongo", "dist_west", "DistWestStore"),
        OrgStore("dist-south", "distributor", "sqlite", "dist_south", "DistSouthStore"),
        OrgStore("shop-delhi", "shop", "sqlite", "shop_delhi", "ShopDelhiStore"),
        OrgStore("shop-mumbai", "shop", "pg", "shop_mumbai", "ShopMumbaiStore"),
        OrgStore("shop-bengaluru", "shop", "mongo", "shop_bengaluru", "ShopBengaluruStore"),
        OrgStore("consumer-delhi", "consumer", "sqlite", "consumer_delhi", "ConsumerDelhiStore"),
        OrgStore("consumer-mumbai", "consumer", "mongo", "consumer_mumbai", "ConsumerMumbaiStore"),
        OrgStore("regulator", "regulator", "pg", "regulator", "RegulatorStore"),
    ]
}


def store_class(org_id: str) -> type:
    spec = ORG_STORES[org_id]
    mod = importlib.import_module(f"asali_node.stores.{spec.module}")
    return getattr(mod, spec.cls)  # type: ignore[no-any-return]


def open_store(org_id: str, target: str, mode: str = "rw", city: str = ""):  # type: ignore[no-untyped-def]
    return store_class(org_id)(target, mode, city)
