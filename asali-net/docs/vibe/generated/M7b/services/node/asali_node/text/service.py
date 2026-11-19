"""One node's text service: ingest into its own vault, mirror links into its database, search for others."""

import asyncio
import contextlib
import logging
from datetime import datetime
from typing import Any

import anyio.from_thread
from asali_text.models import Models
from asali_text.pipeline import ingest

from asali_node.canonical import IST, DocLink
from asali_node.stores.sqlbase import new_id
from asali_node.text.world_online import WorldBuilder
from asali_node.vault.sqlite_vault import Vault

log = logging.getLogger("asali.text")
RELINK_EVERY_S = 600.0
RELINK_WINDOW_S = 90 * 86400


class TextService:
    def __init__(
        self, org_id: str, vault_rw: Vault, vault_ro: Vault, models: Models, builder: WorldBuilder, store: Any
    ) -> None:
        self.org_id, self.rw, self.ro, self.models, self.builder, self.store = (
            org_id,
            vault_rw,
            vault_ro,
            models,
            builder,
            store,
        )

    # ---- writing ----
    async def ingest(self, text: str, *, declared_type: str | None = None, meta: dict[str, Any] | None = None,
                     doc_id: str | None = None, at: datetime | None = None, title: str | None = None,
                     keep_original: bool = False) -> dict[str, Any]:  # fmt: skip
        now = at or datetime.now(IST)
        world, gaz = await self.builder.build(text)
        res = ingest(text, owner_org=self.org_id, declared_type=declared_type, world=world, gaz=gaz, models=self.models,
                     now=now, doc_id=doc_id or new_id("doc_"), title=title, meta=meta)  # fmt: skip
        links = [
            {
                "entity_key": x["entity_key"],
                "entity_type": x["entity_type"],
                "confidence": x["confidence"],
                "because": x["because"],
            }
            for x in res["links"]
        ]
        self.rw.put(res["doc"], links, original=text if keep_original else None)
        self.store.upsert_document_links(res["doc"]["id"], [DocLink(entity_type=x["entity_type"], entity_key=x["entity_key"],
                                                                    confidence=x["confidence"], linked_at=now) for x in links])  # fmt: skip
        return res

    def add(self, doc_id: str, doc_type: str, text: str, meta: dict[str, Any]) -> None:
        """For code that runs in a worker thread (the consumer report route): ingest and wait."""
        at = datetime.fromisoformat(meta["at"]) if meta.get("at") else None
        anyio.from_thread.run(
            lambda: self.ingest(text, declared_type=doc_type, meta=meta, doc_id=doc_id, at=at)
        )

    def add_system(
        self, doc_type: str, text: str, at: datetime | None, meta: dict[str, Any] | None = None
    ) -> None:
        anyio.from_thread.run(
            lambda: self.ingest(
                text, declared_type=doc_type, meta={"system": True, **(meta or {})}, at=at, keep_original=True
            )
        )

    async def relink_once(self) -> int:
        """Run the pipeline again on documents that have no link at 0.8 or more yet."""
        since = int(datetime.now(IST).timestamp()) - RELINK_WINDOW_S
        done = 0
        for d in self.rw.unlinked(since):
            await self.ingest(
                d["body"],
                declared_type=d["doc_type_declared"],
                meta=d["meta"],
                doc_id=d["id"],
                at=datetime.fromtimestamp(d["created_at"], IST),
                title=d["title"],
            )
            done += 1
        return done

    async def relink_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=RELINK_EVERY_S)
            if not stop.is_set():
                try:
                    await self.relink_once()
                except Exception:
                    log.exception("relink failed")

    # ---- reading (the share API uses the read-only vault) ----
    def search(self, params: dict[str, str]) -> list[dict[str, Any]]:
        keys = [k for k in params.get("link_keys", "").split(",") if k]
        types = [t for t in params.get("doc_types", "").split(",") if t]
        hits = self.ro.search(q=params.get("q", ""), link_keys=keys or None, doc_types=types or None,
                              since=int(params["since"]) if params.get("since") else None, limit=min(int(params.get("limit", 20)), 50))  # fmt: skip
        return [{k: v for k, v in h.items() if k != "mentions"} for h in hits]

    def get(self, doc_id: str) -> dict[str, Any] | None:
        return self.ro.get(doc_id)
