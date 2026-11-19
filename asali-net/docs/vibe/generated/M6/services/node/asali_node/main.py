"""One organisation's node. The same code runs as any organisation type; settings decide which."""

from typing import Any

from fastapi import FastAPI

from asali_node import config_api, debug_api
from asali_node.activity import ActivityLog
from asali_node.auth.share_guard import install_share_guard
from asali_node.auth.staff import SessionTable as StaffSessions
from asali_node.auth.staff import seed_staff
from asali_node.documents_store import FileDocuments
from asali_node.logging_setup import configure_logging, install_request_logging
from asali_node.portal import common as portal_common
from asali_node.portal import consumer, holder, pharma, regulator, scan, sim
from asali_node.problems import install_problem_handlers
from asali_node.runtime import network_lifespan
from asali_node.scan_sessions import SessionTable as ScanSessions
from asali_node.settings import Settings
from asali_node.share import common as share_common
from asali_node.share import documents as share_documents
from asali_node.share import roles as share_roles
from asali_node.share import units as share_units
from asali_node.stores.registry import open_store

PORTAL_BY_TYPE = {
    "pharma": [pharma, scan],
    "distributor": [holder, scan],
    "shop": [holder, scan, sim],
    "consumer": [consumer],
    "regulator": [regulator],
}


def open_stores(s: Settings) -> tuple[Any, Any]:
    """The read-write store (portal) and the read-only store (share API), over this org's own database."""
    rw_target = s.db_rw_url or str(s.sqlite_path)
    ro_target = s.db_ro_url or str(s.sqlite_path)
    rw = open_store(s.org_id, rw_target, "rw", s.org_city)
    rw.init_schema()
    return rw, open_store(s.org_id, ro_target, "ro", s.org_city)


def create_app(settings: Settings, rw: Any = None, ro: Any = None) -> FastAPI:
    configure_logging()
    app = FastAPI(title=f"Asali node {settings.org_id}", version="1", lifespan=network_lifespan)
    app.state.settings = settings
    app.state.rw, app.state.ro = rw, ro
    app.state.sessions, app.state.scans = StaffSessions(), ScanSessions()
    app.state.pending = {}  # consumer checks waiting for the person to confirm a corrected code
    app.state.activity = ActivityLog(settings.data_dir)
    app.state.documents = FileDocuments(settings.data_dir)
    if rw is not None:
        seed_staff(rw, settings.staff_seed_json)
    install_problem_handlers(app)
    install_share_guard(app)
    install_request_logging(app, settings.org_id)  # added last, so it wraps the guard and logs 401s
    app.include_router(config_api.router)
    app.include_router(portal_common.router)
    for module in PORTAL_BY_TYPE[settings.org_type]:
        app.include_router(module.router)
    for r in (share_common.router, share_units.router, share_roles.router, share_documents.router):
        app.include_router(r)
    app.include_router(debug_api.router)
    return app


def app_from_env() -> FastAPI:
    settings = Settings()  # type: ignore[call-arg]
    rw, ro = open_stores(settings)
    return create_app(settings, rw, ro)
