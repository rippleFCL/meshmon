import base64
import datetime
from enum import Enum
import json
import os
import time
from fastapi import FastAPI, Depends, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Dict, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets

from distmon.distrostore import NodeData, PingData, SharedStore, SignedNodeData, StoreManager, NodeStatus
from distmon.config import NetworkConfigLoader
from distmon.monitor import MonitorManager
from distmon.conman import ConfigManager
import logging

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d|%(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("distromon.server")  # Create logger for this module
logger = logging.getLogger(__name__)
passlib_logger = logging.getLogger("passlib")
passlib_logger.setLevel(logging.ERROR)  # Suppress passlib debug/info logs
# JWT Configuration
SECRET_KEY = secrets.token_urlsafe(32)  # Generate a random secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
CONFIG_FILE_NAME = os.environ.get("CONFIG_FILE_NAME", "nodeconf.yml")

logger.info(f"Starting server initialization with config file: {CONFIG_FILE_NAME}")

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
security_basic = HTTPBasic()
security_bearer = HTTPBearer()

logger.info("Loading network configuration...")
config = NetworkConfigLoader(file_name=CONFIG_FILE_NAME)
logger.info(f"Loaded {len(config.networks)} network configurations")

logger.info("Initializing store manager...")
store_manager = StoreManager(config, NodeData)
logger.info(f"Initialized store manager with {len(store_manager.stores)} stores")

logger.info("Initializing monitor manager...")
monitor_manager = MonitorManager(store_manager, config)
logger.info(f"Initialized monitor manager with {len(monitor_manager.monitors)} monitors")

logger.info("Initializing config manager...")
config_manager = ConfigManager(config, store_manager, monitor_manager)
logger.info("Config manager initialized")

# Get password from config and hash it
LOGIN_PASSWORD = config.node_cfg.login_password
HASHED_PASSWORD = pwd_context.hash(LOGIN_PASSWORD)
logger.info("Server initialization complete")


app = FastAPI()


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


class ViewData(BaseModel):
    data: dict[str, ViewNodeData] = {}

    @classmethod
    def from_store(cls, store: SharedStore[NodeData]):
        view_data = cls()
        for node_id, node_data in store:
            node = ViewNodeData(node_version=node_data.data.version)
            ping_data = node_data.data.ping_data
            for dest_node_id, ping_result in ping_data.items():
                node.ping_data[dest_node_id] = ViewPingData.from_ping_data(ping_result, dest_node_id)
            view_data.data[node_id] = node
        return view_data


class Token(BaseModel):
    access_token: str
    token_type: str


def authenticate_user(username: str, password: str) -> None | str:
    """Authenticate a user by username and password."""
    logger.debug(f"Authentication attempt for username: {username}")
    # Only accept 'admin' username and check against hashed config password
    if username != "admin":
        logger.warning(f"Authentication failed: invalid username '{username}'")
        return None
    if not pwd_context.verify(password, HASHED_PASSWORD):
        logger.warning(f"Authentication failed: invalid password for user '{username}'")
        return None
    logger.debug(f"Authentication successful for user: {username}")
    return username


def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Create a JWT access token."""
    logger.debug(f"Creating access token for data: {data}")
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.debug(f"Access token created, expires at: {expire}")
    return encoded_jwt


@app.post("/token", response_model=Token)
async def login_for_access_token(credentials: HTTPBasicCredentials = Depends(security_basic)):
    """Login endpoint that accepts HTTP Basic Auth and returns JWT token."""
    user = authenticate_user(credentials.username, credentials.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    access_token_expires = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security_bearer)) -> None:
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None or username != "admin":
            raise credentials_exception
    except JWTError:
        raise credentials_exception


def validate_msg(body: MonBody, network_id: str, authorization: str) -> dict:
    """Validate message signature using the existing crypto verification system."""
    logger.debug(f"Validating message for network {network_id}, sig_id: {body.sig_id}")
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning(f"Invalid authorization header for network {network_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Bearer token")

    store = store_manager.get_store(network_id)
    if not store:
        logger.warning(f"Network not found: {network_id}")
        raise HTTPException(status_code=404, detail="Network not found")

    verifier = store.key_mapping.get_verifier(body.sig_id)
    if not verifier:
        logger.warning(f"No verifier found for sig_id: {body.sig_id} in network {network_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    header = authorization.removeprefix("Bearer ")

    if not verifier.verify(json.dumps(body.data).encode(), base64.b64decode(header)):
        logger.warning(f"Signature verification failed for sig_id: {body.sig_id} in network {network_id}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    logger.debug(f"Message validation successful for {network_id}, sig_id: {body.sig_id}")
    return body.data


@app.post("/mon/{network_id}", response_model=StoreResponse)
def mon(body: MonBody, network_id: str, authorization: str = Header()):
    logger.debug(f"Received monitoring data for network: {network_id}, sig_id: {body.sig_id}")
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
    return StoreResponse.model_validate({"store_data": raw, "ms_send_time": diff * 1000})


@app.get("/view/{network_id}", response_model=ViewData)
def view(network_id: str, _: None = Depends(validate_token)):
    """Get network view data. Requires JWT authentication."""
    logger.debug(f"View request for network: {network_id}")
    mon_store = store_manager.get_store(network_id)
    return ViewData.from_store(mon_store)
