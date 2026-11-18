"""One organisation's node. The same code runs as any organisation type; settings decide which."""

from fastapi import FastAPI

from asali_node import config_api
from asali_node.logging_setup import configure_logging, install_request_logging
from asali_node.problems import install_problem_handlers
from asali_node.settings import Settings
from asali_node.share import common as share_common


def create_app(settings: Settings) -> FastAPI:
    configure_logging()
    app = FastAPI(title=f"Asali node {settings.org_id}", version="1")
    app.state.settings = settings
    install_problem_handlers(app)
    install_request_logging(app, settings.org_id)
    app.include_router(config_api.router)
    app.include_router(share_common.router)
    return app


def app_from_env() -> FastAPI:
    return create_app(Settings())  # type: ignore[call-arg]
