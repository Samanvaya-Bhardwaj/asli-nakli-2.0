"""One organisation's node. The same code runs as any organisation type; settings decide which."""

from fastapi import FastAPI

from asali_node import config_api, debug_api
from asali_node.auth.share_guard import install_share_guard
from asali_node.logging_setup import configure_logging, install_request_logging
from asali_node.problems import install_problem_handlers
from asali_node.runtime import network_lifespan
from asali_node.settings import Settings
from asali_node.share import common as share_common


def create_app(settings: Settings) -> FastAPI:
    configure_logging()
    app = FastAPI(title=f"Asali node {settings.org_id}", version="1", lifespan=network_lifespan)
    app.state.settings = settings
    install_problem_handlers(app)
    install_share_guard(app)
    install_request_logging(app, settings.org_id)  # added last, so it wraps the guard and logs 401s
    app.include_router(config_api.router)
    app.include_router(share_common.router)
    app.include_router(debug_api.router)
    return app


def app_from_env() -> FastAPI:
    return create_app(Settings())  # type: ignore[call-arg]
