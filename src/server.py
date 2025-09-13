import base64
import json
import os
import time
from fastapi import FastAPI, Header, HTTPException, status

from pydantic import BaseModel
from typing import Any, Dict

from meshmon.distrostore import (
    NodeData,
    PingData,
    SharedStore,
    SignedNodeData,
    StoreManager,
    NodeStatus,
)
from meshmon.config import NetworkConfigLoader
from meshmon.monitor import MonitorManager
from meshmon.conman import ConfigManager
import logging

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

logger.info(f"Starting server initialization with config file: {CONFIG_FILE_NAME}")


logger.info("Loading network configuration...")
config = NetworkConfigLoader(file_name=CONFIG_FILE_NAME)
logger.info(f"Loaded {len(config.networks)} network configurations")

logger.info("Initializing store manager...")
store_manager = StoreManager(config, NodeData)
logger.info(f"Initialized store manager with {len(store_manager.stores)} stores")

logger.info("Initializing monitor manager...")
monitor_manager = MonitorManager(store_manager, config)
logger.info(
    f"Initialized monitor manager with {len(monitor_manager.monitors)} monitors"
)

logger.info("Initializing config manager...")
config_manager = ConfigManager(config, store_manager, monitor_manager)
logger.info("Config manager initialized")

# Get password from config and hash it
logger.info("Server initialization complete")


api = FastAPI()


class StoreResponse(BaseModel):
    store_data: Dict[str, SignedNodeData[Any]]
    ms_send_time: float


class MonBody(BaseModel):
    data: dict
    sig_id: str
    send_time: float


class ViewPingData(BaseModel):
    status: NodeStatus
    response_time: float
    response_time_rtt: float

    @classmethod
    def from_ping_data(cls, data: PingData, node_id: str):
        return cls(
            status=data.status,
            response_time=data.req_time_outbound,
            response_time_rtt=data.req_time_rtt,
        )


class ViewNodeData(BaseModel):
    ping_data: dict[str, ViewPingData] = {}
    node_version: str


class ViewNetwork(BaseModel):
    data: dict[str, ViewNodeData] = {}

    @classmethod
    def from_store(cls, store: SharedStore[NodeData]):
        view_data = cls()
        for node_id, node_data in store:
            node = ViewNodeData(node_version=node_data.data.version)
            ping_data = node_data.data.ping_data
            for dest_node_id, ping_result in ping_data.items():
                node.ping_data[dest_node_id] = ViewPingData.from_ping_data(
                    ping_result, dest_node_id
                )
            view_data.data[node_id] = node
        return view_data


class ViewData(BaseModel):
    networks: dict[str, ViewNetwork] = {}


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


@api.post("/mon/{network_id}", response_model=StoreResponse)
def mon(body: MonBody, network_id: str, authorization: str = Header()):
    logger.debug(
        f"Received monitoring data for network: {network_id}, sig_id: {body.sig_id}"
    )
    now = time.time()
    send_time = body.send_time
    diff = now - send_time
    logger.debug(f"Request processing delay: {diff * 1000:.2f}ms")
    msg = validate_msg(body, network_id, authorization)
    mon_store = store_manager.get_store(network_id)
    mon_store.update_from_dump(msg)
    raw = mon_store.dump()

    logger.debug(f"Successfully processed monitoring data for {network_id}")
    # Convert each value to SignedNodeData
    return StoreResponse.model_validate(
        {"store_data": raw, "ms_send_time": diff * 1000}
    )


@api.get("/view", response_model=ViewData)
def view():
    """Get network view data. Requires JWT authentication."""
    logger.debug("View request for networks")
    networks = ViewData()
    for network_id, store in store_manager.stores.items():
        networks.networks[network_id] = ViewNetwork.from_store(store)

    return networks
