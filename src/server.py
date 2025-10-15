import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import FileResponse

from meshmon.api.processor import (
    generate_api,
    generate_cluster_api,
    generate_notification_cluster_info,
)
from meshmon.api.structure.cluster_info import ClusterInfoApi
from meshmon.api.structure.notification_cluster import NotificationClusterApi
from meshmon.api.structure.status import (
    MeshMonApi,
)
from meshmon.config.bus import ConfigBus
from meshmon.config.config import (
    NetworkConfigLoader,
)
from meshmon.connection.grpc_server import GrpcServer
from meshmon.connection.heartbeat import HeartbeatController
from meshmon.distrostore import (
    StoreManager,
)
from meshmon.dstypes import (
    DSNodeStatus,
    DSPingData,
)
from meshmon.lifecycle import LifecycleManager
from meshmon.monitor import MonitorManager
from meshmon.pulsewave.store import (
    StoreData,
)
from meshmon.version import VERSION
from meshmon.webhooks import WebhookManager

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
environment = os.environ.get("ENV", "prod").lower()
# Map textual levels to numeric for structlog filtering without importing logging
_LEVELS = {
    "CRITICAL": 50,
    "ERROR": 40,
    "WARNING": 30,
    "INFO": 20,
    "DEBUG": 10,
}
if environment == "dev":
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
        structlog.dev.ConsoleRenderer(),
    ]
else:
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=False),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
        structlog.processors.JSONRenderer(sort_keys=True),
    ]

structlog.configure_once(
    processors=processors,
    logger_factory=structlog.PrintLoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(_LEVELS.get(log_level, 20)),
    cache_logger_on_first_use=True,
)
logger = structlog.stdlib.get_logger()

# JWT Configuration
CONFIG_FILE_NAME = os.environ.get("CONFIG_FILE_NAME", "nodeconf.yml")


logger.info("Starting server initialization with config file", config=CONFIG_FILE_NAME)

logger.info("Initializing configuration loader...")
config_loader = NetworkConfigLoader(file_name=CONFIG_FILE_NAME)

logger.info("Setting up configuration bus...")
config_bus = ConfigBus()

logger.info("Initializing gRPC server...")
grpc_server = GrpcServer(config_bus)

logger.info("Initializing store manager...")
store_manager = StoreManager(config_bus, grpc_server)

logger.info("Initializing Heartbeat controller...")
heartbeat_controller = HeartbeatController(
    grpc_server.connection_manager, config_bus, store_manager
)

logger.info("Initializing monitor manager...")
monitor_manager = MonitorManager(store_manager, config_bus)

logger.info("Initializing webhook manager...")
webhook_manager = WebhookManager(store_manager, config_bus)

logger.info("Initializing config manager...")
lifecycle_manager = LifecycleManager(
    config_loader,
    webhook_manager,
    store_manager,
    grpc_server,
    monitor_manager,
    heartbeat_controller,
    config_bus,
)

logger.info("Server initialization complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up the server...")
    lifecycle_manager.start()
    yield
    logger.info("Shutting down the server...")
    lifecycle_manager.stop()


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
    status: DSNodeStatus
    response_time_rtt: float

    @classmethod
    def from_ping_data(cls, data: DSPingData, node_id: str):
        return cls(
            status=data.status,
            response_time_rtt=data.req_time_rtt,
        )


class ViewNetwork(BaseModel):
    networks: dict[str, StoreData] = {}


@api.get("/api/view", response_model=MeshMonApi)
def view():
    """Get network view data. Requires JWT authentication."""
    logger.debug("View request for networks")
    networks = generate_api(store_manager, config_loader.config)
    return networks


@api.get("/api/cluster", response_model=ClusterInfoApi)
def cluster_view():
    """Get cluster view data. Requires JWT authentication."""
    logger.debug("Cluster view request for networks")
    networks = generate_cluster_api(store_manager)
    return networks


@api.get("/api/notification_cluster", response_model=NotificationClusterApi)
def notification_cluster_view():
    """Get notification cluster view data. Requires JWT authentication."""
    logger.debug("Notification cluster view request for networks")
    networks = generate_notification_cluster_info(store_manager)
    return networks


@api.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "version": VERSION}


@api.get("/api/raw/{network_id}", response_model=StoreData)
def get_raw_store(network_id: str):
    """Get raw store data for a specific network. Requires JWT authentication."""
    logger.debug("Raw store request for network", net_id=network_id)
    store = store_manager.get_store(network_id)
    if not store:
        logger.warning("Network not found", net_id=network_id)
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
