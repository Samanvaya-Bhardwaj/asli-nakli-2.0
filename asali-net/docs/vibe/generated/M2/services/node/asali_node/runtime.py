"""Start-up and shut-down of a node's network side: keys, directory registration, heartbeat, share client."""

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from asali_node.auth.signing import load_or_create_keys
from asali_node.directory_client import DirectoryClient
from asali_node.network.client import ShareClient
from asali_node.settings import Settings

log = logging.getLogger("asali.runtime")
REGISTER_RETRY_S = 5.0


async def _join(directory: DirectoryClient, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await directory.register()
            log.info(json.dumps({"event": "registered"}))
            break
        except httpx.HTTPError as e:
            log.warning(json.dumps({"event": "register_failed", "error": type(e).__name__}))
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=REGISTER_RETRY_S)
    await directory.heartbeat_loop(stop=stop)


@asynccontextmanager
async def network_lifespan(app: FastAPI) -> AsyncIterator[None]:
    s: Settings = app.state.settings
    key = load_or_create_keys(s.data_dir)
    http = httpx.AsyncClient()  # honours SSL_CERT_FILE, so the team's mkcert CA is trusted
    directory = DirectoryClient(s, key, http)
    app.state.directory = directory
    app.state.key_lookup = directory.public_key
    app.state.refresh_directory = directory.refresh
    app.state.share = ShareClient(s.org_id, key, http, directory.base_url, on_unknown=directory.refresh)
    stop = asyncio.Event()
    task = asyncio.create_task(_join(directory, stop))
    try:
        yield
    finally:
        stop.set()
        await task
        await http.aclose()
