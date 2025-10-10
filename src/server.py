import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import FileResponse

from meshmon.api.processor import generate_api
from meshmon.api.structure import (
    MeshMonApi,
)
from meshmon.config import (
    NetworkConfigLoader,
)
from meshmon.conman import ConfigManager
from meshmon.connection.grpc_server import GrpcServer
from meshmon.connection.heartbeat import HeartbeatController
from meshmon.distrostore import (
    StoreManager,
)
from meshmon.dstypes import (
    DSNodeInfo,
    DSNodeStatus,
    DSPingData,
)
from meshmon.monitor import MonitorManager
from meshmon.pulsewave.store import (
    StoreData,
)
from meshmon.version import VERSION
from meshmon.webhooks import WebhookHandler

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


logger.info("Loading network configuration...")
config = NetworkConfigLoader(file_name=CONFIG_FILE_NAME)
logger.info("Loaded network configurations", count=len(config.networks))

logger.info("Initializing gRPC server...")
grpc_server = GrpcServer(config)
logger.info("gRPC server initialized")

logger.info("Initializing store manager...")
store_manager = StoreManager(config, grpc_server)
logger.info("Initialized store manager with stores", count=len(store_manager.stores))

logger.info("Initializing Heartbeat controller...")
heartbeat_controller = HeartbeatController(
    grpc_server.connection_manager, config, store_manager
)
logger.info("Heartbeat controller initialized")

logger.info("Initializing monitor manager...")
monitor_manager = MonitorManager(store_manager, config)
logger.info(
    f"Initialized monitor manager with {len(monitor_manager.monitors)} monitors"
)

logger.info("Initializing webhook handler...")
webhook_handler = WebhookHandler(store_manager, config)
logger.info("Webhook handler initialized")

logger.info("Initializing config manager...")
config_manager = ConfigManager(config, store_manager)
logger.info("Config manager initialized")

# Get password from config and hash it
logger.info("Server initialization complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up the server...")
    grpc_server.start()
    heartbeat_controller.start()
    yield
    heartbeat_controller.stop()
    webhook_handler.stop()
    monitor_manager.stop_manager()
    for net_id, store in store_manager.stores.items():
        node_info = DSNodeInfo(version=VERSION)
        store.set_value("node_info", node_info)
    grpc_server.stop()
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
    status: DSNodeStatus
    response_time_rtt: float

    @classmethod
    def from_ping_data(cls, data: DSPingData, node_id: str):
        return cls(
            status=data.status,
            response_time_rtt=data.req_time_rtt,
        )


# def validate_msg(body: MonBody, network_id: str, authorization: str) -> dict:
#     """Validate message signature using the existing crypto verification system."""
#     logger.debug(
#         "Validating message for network", net_id=network_id, sig_id=body.sig_id
#     )
#     if not authorization or not authorization.startswith("Bearer "):
#         logger.warning("Invalid authorization header for network", net_id=network_id)
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Missing or invalid Bearer token",
#         )
#
#     store = store_manager.get_store(network_id)
#     if not store:
#         logger.warning("Network not found", net_id=network_id)
#         raise HTTPException(status_code=404, detail="Network not found")
#
#     verifier = store.key_mapping.get_verifier(body.sig_id)
#     if not verifier:
#         logger.warning(
#             f"No verifier found for sig_id: {body.sig_id} in network {network_id}"
#         )
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
#         )
#
#     header = authorization.removeprefix("Bearer ")
#
#     if not verifier.verify(json.dumps(body.data).encode(), base64.b64decode(header)):
#         logger.warning(
#             f"Signature verification failed for sig_id: {body.sig_id} in network {network_id}"
#         )
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
#         )
#
#     logger.debug(
#         f"Message validation successful for {network_id}, sig_id: {body.sig_id}"
#     )
#     return body.data


class ViewNetwork(BaseModel):
    networks: dict[str, StoreData] = {}


@api.get("/api/view", response_model=MeshMonApi)
def view():
    """Get network view data. Requires JWT authentication."""
    logger.debug("View request for networks")
    networks = generate_api(store_manager, config)
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
