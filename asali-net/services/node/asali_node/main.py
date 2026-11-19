"""One organisation's node. The same code runs as any organisation type; settings decide which."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from asali_node import config_api, debug_api
from asali_node.activity import ActivityLog
from asali_node.auth.share_guard import install_share_guard
from asali_node.auth.staff import SessionTable as StaffSessions
from asali_node.auth.staff import seed_staff
from asali_node.canonical import Alert
from asali_node.documents_store import FileDocuments
from asali_node.logging_setup import configure_logging, install_request_logging
from asali_node.portal import common as portal_common
from asali_node.portal import consumer, holder, pharma, regulator, scan, sim
from asali_node.portal import documents as portal_documents
from asali_node.portal import network as portal_network
from asali_node.problems import install_problem_handlers
from asali_node.runtime import network_lifespan
from asali_node.scan_sessions import SessionTable as ScanSessions
from asali_node.settings import Settings
from asali_node.share import common as share_common
from asali_node.share import documents as share_documents
from asali_node.share import roles as share_roles
from asali_node.share import units as share_units
from asali_node.stores.registry import open_store
from asali_node.text import system_docs
from asali_node.text.service import TextService
from asali_node.text.world_online import WorldBuilder
from asali_node.vault.sqlite_vault import Vault

log = logging.getLogger("asali.node")
PORTAL_BY_TYPE = {
    "pharma": [pharma, scan],
    "distributor": [holder, scan],
    "shop": [holder, scan, sim],
    "consumer": [consumer],
    "regulator": [regulator],
}
STAFF_DOCUMENTS = {"pharma", "distributor", "shop", "regulator"}


def open_stores(s: Settings) -> tuple[Any, Any]:
    """The read-write store (portal) and the read-only store (share API), over this org's own database."""
    rw_target = s.db_rw_url or str(s.sqlite_path)
    ro_target = s.db_ro_url or str(s.sqlite_path)
    rw = open_store(s.org_id, rw_target, "rw", s.org_city)
    rw.init_schema()
    return rw, open_store(s.org_id, ro_target, "ro", s.org_city)


def attach_text(app: FastAPI, settings: Settings, rw: Any) -> TextService | None:
    """Turn on the text pipeline when trained models are available; otherwise reports go to a plain file store."""

    if settings.ml_models_dir is None or not (settings.ml_models_dir / "meta.json").exists():
        log.warning("text pipeline is off: no trained models at %s", settings.ml_models_dir)
        return None
    vault_rw, vault_ro = Vault(settings.data_dir, "rw"), None
    vault_ro = Vault(settings.data_dir, "ro")
    builder = WorldBuilder(app.state, rw, settings.org_id, settings.org_type)
    service = TextService(settings.org_id, vault_rw, vault_ro, settings.ml_models_dir, builder, rw)
    app.state.text, app.state.documents = service, service
    hooks(app, settings, service, rw)
    return service


def hooks(app: FastAPI, settings: Settings, service: TextService, rw: Any) -> None:
    """The documents the system writes by itself (TEXT_ML.md 3)."""

    def names() -> dict[str, str]:
        return {o["org_id"]: o["name"] for o in app.state.directory.known()}

    def on_recall(gtin: str, lot: str, reason: str, level: str, at: datetime) -> None:
        p = next((x for x in rw.products() if x.gtin == gtin), None)
        text = system_docs.recall_notice(
            settings.org_name, p.brand if p else gtin, p.strength if p else "", lot, reason, level, at
        )
        service.add_system("recall_notice", text, at)

    def on_alert(alert: Alert) -> None:
        if alert.lot:
            doc_type, text = system_docs.regulator_notice(
                alert, names().get(alert.manufacturer_org, alert.manufacturer_org)
            )
            service.add_system(doc_type, text, alert.issued_at)

    def on_discrepancy(
        from_org: str, ref: str, missing: list[str], at: datetime, expected: int, received: int
    ) -> None:
        text = system_docs.discrepancy_note(settings.org_name, ref, expected, received, missing)
        service.add_system("discrepancy_note", text, at)

    app.state.on_recall, app.state.on_alert, app.state.on_discrepancy = on_recall, on_alert, on_discrepancy


def create_app(settings: Settings, rw: Any = None, ro: Any = None, with_text: bool = False) -> FastAPI:
    configure_logging()
    app = FastAPI(title=f"Asali node {settings.org_id}", version="1", lifespan=network_lifespan)
    app.state.settings = settings
    app.state.rw, app.state.ro = rw, ro
    app.state.sessions, app.state.scans = StaffSessions(), ScanSessions()
    app.state.pending = {}  # consumer checks waiting for the person to confirm a corrected code
    app.state.activity = ActivityLog(settings.data_dir)
    app.state.documents = FileDocuments(settings.data_dir)
    app.state.text = None
    if rw is not None:
        seed_staff(rw, settings.staff_seed_json)
        if with_text:
            attach_text(app, settings, rw)
    install_problem_handlers(app)
    install_share_guard(app)
    install_request_logging(app, settings.org_id)  # added last, so it wraps the guard and logs 401s
    app.include_router(config_api.router)
    app.include_router(portal_common.router)
    app.include_router(portal_network.router)
    for module in PORTAL_BY_TYPE[settings.org_type]:
        app.include_router(module.router)
    if settings.org_type in STAFF_DOCUMENTS:
        app.include_router(portal_documents.router)
    for r in (share_common.router, share_units.router, share_roles.router, share_documents.router):
        app.include_router(r)
    app.include_router(debug_api.router)
    if settings.web_dir is not None and (settings.web_dir / "index.html").exists():
        mount_web(app, settings.web_dir)
    return app


def app_from_env() -> FastAPI:
    settings = Settings()  # type: ignore[call-arg]
    rw, ro = open_stores(settings)
    return create_app(settings, rw, ro, with_text=True)


def mount_web(app: FastAPI, web_dir: Path) -> None:
    """Serve the built portal. Any other path that is not the API gets index.html, so deep links work."""
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    if (web_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=web_dir / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith(("api/", "share/")):
            raise HTTPException(404)
        target = web_dir / path
        return FileResponse(target if path and target.is_file() else web_dir / "index.html")
