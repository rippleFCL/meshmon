# distomon Code Architecture

This document explains the architecture and code structure of distomon, a distributed monitoring solution.

## System Overview

distomon is a distributed monitoring system where nodes monitor each other's health and status. Each node runs a FastAPI server that communicates with other nodes in the network using cryptographically signed messages.

```mermaid
graph TB
    A[Node A] -->|Monitors| B[Node B]
    B -->|Monitors| C[Node C]
    C -->|Monitors| A
    A -->|Monitors| C

    subgraph "Node A Components"
        A1[FastAPI Server]
        A2[Monitor Manager]
        A3[Store Manager]
        A4[Config Manager]
    end

    subgraph "Network Config"
        N1[Local Config]
        N2[GitHub Config]
    end

    N1 --> A1
    N2 --> A1
```

## Core Components

### 1. Server (`server.py`)

The main FastAPI application that handles HTTP requests and coordinates all other components.

**Key responsibilities:**
- Initialize managers (Store, Monitor, Config)
- Handle authentication (JWT and Basic Auth)
- Provide API endpoints for monitoring data exchange
- Manage environment configuration

```mermaid
sequenceDiagram
    participant Client
    participant Server
    participant StoreManager
    participant MonitorManager

    Client->>Server: POST /mon/{network_id}
    Server->>Server: Verify signature
    Server->>StoreManager: Update node data
    Server->>MonitorManager: Process monitoring data
    Server->>Client: Response with local data
```

### 2. Monitor Manager (`monitor.py`)

Manages monitoring threads that periodically check the health of remote nodes.

**Key components:**
- `Monitor`: Individual monitoring thread for a specific remote node
- `MonitorManager`: Coordinates all monitoring threads across networks

```mermaid
stateDiagram-v2
    [*] --> Initialized
    Initialized --> Running: start()
    Running --> Monitoring: monitor()
    Monitoring --> SendingRequest: POST to remote node
    SendingRequest --> ProcessingResponse: Handle response
    ProcessingResponse --> UpdatingStore: Update node status
    UpdatingStore --> Waiting: Sleep(poll_rate)
    Waiting --> Monitoring: Wake up
    ProcessingResponse --> HandleError: Request failed
    HandleError --> UpdatingStore: Mark as offline
    Running --> Stopped: stop()
    Stopped --> [*]
```

**Monitor workflow:**
1. Load store data and sign it
2. Send POST request to remote node's `/mon/{network_id}` endpoint
3. Process response and update local store with remote node's status
4. Handle errors and mark nodes offline if unreachable
5. Sleep for `poll_rate` seconds and repeat

### 3. Store Manager (`distrostore.py`)

Manages distributed storage of node data across different networks.

**Key classes:**
- `NodeData`: Contains ping data, node ID, timestamp, and version
- `SignedNodeData`: Cryptographically signed node data
- `SharedStore`: In-memory storage for a single network
- `StoreManager`: Manages multiple stores across networks

```mermaid
classDiagram
    class NodeData {
        +dict ping_data
        +str node_id
        +datetime date
        +str version
    }

    class SignedNodeData {
        +T data
        +str signature
        +str sig_id
        +new(signer, data)
        +verify(verifier)
    }

    class SharedStore {
        +KeyMapping key_mapping
        +dict node_data
        +update(signed_data)
        +dump()
    }

    class StoreManager {
        +dict stores
        +get_store(network_id)
    }

    NodeData --> SignedNodeData
    SignedNodeData --> SharedStore
    SharedStore --> StoreManager
```

### 4. Configuration Manager (`config.py`)

Handles loading and managing network configurations from local files or GitHub repositories.

**Key features:**
- Support for local and GitHub-based configurations
- Automatic Git repository cloning/pulling
- Cryptographic key management
- Network topology definition

```mermaid
flowchart TD
    A[nodeconf.yml] --> B{Config Type}
    B -->|local| C[Load Local Config]
    B -->|github| D[Clone/Pull Git Repo]
    D --> E[Load Remote Config]
    C --> F[Load Network Config]
    E --> F
    F --> G[Load Cryptographic Keys]
    G --> H[Create Network Config]
    H --> I[Initialize Monitors]
```

**Configuration structure:**
```yaml
networks:
  - name: test
    node_id: seeg
    config_type: github
    git_repo: https://github.com/rippleFCL/distmon-test.git
login_password: password
```

### 5. Cryptographic System (`crypto.py`)

Provides Ed25519 signing and verification for secure message exchange.

**Key classes:**
- `Signer`: Signs outgoing messages
- `Verifier`: Verifies incoming messages
- `KeyMapping`: Maps node IDs to their cryptographic keys

```mermaid
sequenceDiagram
    participant NodeA
    participant NodeB

    Note over NodeA: Prepare monitoring data
    NodeA->>NodeA: Sign data with private key
    NodeA->>NodeB: Send signed data
    NodeB->>NodeB: Verify signature with NodeA's public key
    NodeB->>NodeB: Process data if valid
    NodeB->>NodeB: Sign response with private key
    NodeB->>NodeA: Send signed response
    NodeA->>NodeA: Verify signature with NodeB's public key
```

## Data Flow

### Monitoring Cycle

```mermaid
flowchart LR
    A[Monitor Thread] --> B[Get Local Store Data]
    B --> C[Sign Data]
    C --> D[POST to Remote Node]
    D --> E[Receive Response]
    E --> F[Verify Response]
    F --> G[Update Local Store]
    G --> H[Sleep poll_rate]
    H --> A

    D --> I[Request Failed]
    I --> J[Mark Node Offline]
    J --> H
```

### API Endpoints

The server exposes several endpoints:

- `POST /mon/{network_id}`: Exchange monitoring data between nodes
- `GET /store/{network_id}`: Retrieve current store data
- `POST /login`: Authenticate and get JWT token
- `GET /info`: Get node information

### Error Handling

The system includes comprehensive error handling:

1. **Network errors**: Nodes marked offline after retry limit exceeded
2. **Signature verification**: Invalid signatures rejected
3. **Configuration errors**: Graceful fallbacks and logging
4. **Threading**: Daemon threads prevent hanging on shutdown

## Security Model

1. **Cryptographic Signing**: All inter-node communication is signed with Ed25519
2. **Authentication**: API endpoints protected with JWT tokens
3. **Key Management**: Public keys stored per network, private keys local only
4. **Signature Verification**: All incoming data verified before processing

This architecture provides a robust, secure, and scalable distributed monitoring solution that can adapt to various network topologies and requirements.
