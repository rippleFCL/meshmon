import base64
from contextlib import asynccontextmanager
import datetime
import json
import os
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse
from pydantic import BaseModel

from meshmon.distrostore import (
    DateEvalType,
    NodeInfo,
    PingData,
    StoreData,
    StoreManager,
    NodeStatus,
    NodeDataRetention,
    SharedStore,
)
from meshmon.update import UpdateManager
from meshmon.config import (
    NetworkConfig,
    NetworkConfigLoader,
    get_pingable_nodes,
    get_all_monitor_names,
)
from meshmon.monitor import MonitorManager
from meshmon.conman import ConfigManager
from meshmon.version import VERSION
from meshmon.analysis.analysis import MultiNetworkAnalysis, analyze_all_networks
import logging
from meshmon.webhooks import WebhookHandler, AnalysedNodeStatus
from fastapi.staticfiles import StaticFiles

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d|%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("meshmon.server")  # Create logger for this module
logger = logging.getLogger(__name__)

# JWT Configuration
CONFIG_FILE_NAME = os.environ.get("CONFIG_FILE_NAME", "nodeconf.yml")


def prefill_store(store: SharedStore, network: NetworkConfig):
    node_info = NodeInfo(status=NodeStatus.ONLINE, version=VERSION)
    store.set_value("node_info", node_info)
    data_retention = NodeDataRetention(
        date=datetime.datetime.now(datetime.timezone.utc)
    )
    store.set_value("data_retention", data_retention, DateEvalType.OLDER)
    ctx = store.get_context("ping_data", PingData)
    ctx.allowed_keys = get_pingable_nodes(network)
    ctx = store.get_context("last_notified_status", AnalysedNodeStatus)
    ctx.allowed_keys = list(network.key_mapping.verifiers.keys())
    ctx = store.get_context("network_analysis", AnalysedNodeStatus)
    ctx.allowed_keys = list(network.key_mapping.verifiers.keys())
    ctx = store.get_context("monitor_data", PingData)
    ctx.allowed_keys = get_all_monitor_names(network, store.key_mapping.signer.node_id)
    ctx = store.get_context("monitor_analysis", AnalysedNodeStatus)
    ctx.allowed_keys = get_all_monitor_names(network, store.key_mapping.signer.node_id)


logger.info(f"Starting server initialization with config file: {CONFIG_FILE_NAME}")


logger.info("Loading network configuration...")
config = NetworkConfigLoader(file_name=CONFIG_FILE_NAME)
logger.info(f"Loaded {len(config.networks)} network configurations")

logger.info("Initializing store manager...")
store_manager = StoreManager(config, prefill_store)
logger.info(f"Initialized store manager with {len(store_manager.stores)} stores")

logger.info("Initializing update manager...")
update_manager = UpdateManager(store_manager, config)
logger.info("Update manager initialized")

logger.info("Initializing monitor manager...")
monitor_manager = MonitorManager(store_manager, config, update_manager)
logger.info(
    f"Initialized monitor manager with {len(monitor_manager.monitors)} monitors"
)

logger.info("Initializing webhook handler...")
webhook_handler = WebhookHandler(store_manager, config, update_manager)
logger.info("Webhook handler initialized")

logger.info("Initializing config manager...")
config_manager = ConfigManager(config, store_manager, monitor_manager, update_manager)
logger.info("Config manager initialized")

# Get password from config and hash it
logger.info("Server initialization complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up the server...")
    yield
    webhook_handler.stop()
    monitor_manager.stop_manager()
    for net_id, store in store_manager.stores.items():
        node_info = NodeInfo(status=NodeStatus.OFFLINE, version=VERSION)
        store.set_value("node_info", node_info)
        update_manager.update(net_id)
    update_manager.stop()
    monitor_manager.stop()


api = FastAPI(lifespan=lifespan)

if os.environ.get("ENV", "") != "production":
    # Add CORS middleware
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # Allow the Vite dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class MonBody(BaseModel):
    data: dict
    sig_id: str


class ViewPingData(BaseModel):
    status: NodeStatus
    response_time_rtt: float

    @classmethod
    def from_ping_data(cls, data: PingData, node_id: str):
        return cls(
            status=data.status,
            response_time_rtt=data.req_time_rtt,
        )


def validate_msg(body: MonBody, network_id: str, authorization: str) -> dict:
    """Validate message signature using the existing crypto verification system."""
    logger.debug(f"Validating message for network {network_id}, sig_id: {body.sig_id}")
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning(f"Invalid authorization header for network {network_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Bearer token",
        )

    store = store_manager.get_store(network_id)
    if not store:
        logger.warning(f"Network not found: {network_id}")
        raise HTTPException(status_code=404, detail="Network not found")

    verifier = store.key_mapping.get_verifier(body.sig_id)
    if not verifier:
        logger.warning(
            f"No verifier found for sig_id: {body.sig_id} in network {network_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    header = authorization.removeprefix("Bearer ")

    if not verifier.verify(json.dumps(body.data).encode(), base64.b64decode(header)):
        logger.warning(
            f"Signature verification failed for sig_id: {body.sig_id} in network {network_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )

    logger.debug(
        f"Message validation successful for {network_id}, sig_id: {body.sig_id}"
    )
    return body.data


@api.post("/api/mon/{network_id}", response_model=StoreData)
def mon(body: MonBody, network_id: str, authorization: str = Header()):
    logger.debug(
        f"Received monitoring data for network: {network_id}, sig_id: {body.sig_id}"
    )
    msg = validate_msg(body, network_id, authorization)
    mon_store = store_manager.get_store(network_id)
    updated = mon_store.update_from_dump(msg)
    if updated:
        logger.info(f"Store updated from dump received for network: {network_id}")
        update_manager.update(network_id)
    logger.debug(f"Successfully processed monitoring data for {network_id}")
    # Convert each value to SignedNodeData
    return mon_store.store


class ViewNetwork(BaseModel):
    networks: dict[str, StoreData] = {}


@api.get("/api/view", response_model=MultiNetworkAnalysis)
def view():
    """Get network view data. Requires JWT authentication."""
    logger.debug("View request for networks")
    networks = analyze_all_networks(store_manager, config)
    return networks


@api.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "version": VERSION}


@api.get("/api/raw/{network_id}", response_model=StoreData)
def get_raw_store(network_id: str):
    """Get raw store data for a specific network. Requires JWT authentication."""
    logger.debug(f"Raw store request for network: {network_id}")
    store = store_manager.get_store(network_id)
    if not store:
        logger.warning(f"Network not found: {network_id}")
        raise HTTPException(status_code=404, detail="Network not found")
    return store.store


if os.path.exists("static"):
    api.mount(
        "/assets", StaticFiles(directory="static/assets", html=True), name="static"
    )

    @api.get("/{full_path:path}")
    async def catch_all(full_path: str, accept: str = Header(default="")):
        if accept and "text/html" not in accept:
            return HTTPException(status_code=404, detail="Not Found")
        return FileResponse("static/index.html")
else:
    logger.warning("Static directory 'static/assets' does not exist.")
