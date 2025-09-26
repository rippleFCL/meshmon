# meshmon

<p align="center">
  <strong>Distributed peer-to-peer monitoring system with cryptographic security</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.2.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/python-3.13+-green.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/license-MIT-orange.svg" alt="License">
</p>

---

## Introduction

**meshmon** is a distributed monitoring system designed to create resilient networks of nodes that monitor each other's health and status. It provides secure, scalable, and extensible peer-to-peer monitoring with built-in cryptographic verification and flexible configuration management.

### Key Benefits

- **Secure**: Ed25519 cryptographic signing ensures data authenticity
- **Mesh Architecture**: No single point of failure - nodes monitor each other
- **Flexible**: Support for local and remote Git-based configurations

## Screenshots

### Dashboard Overview
<p align="center">
  <img src="screenshots/dashboard.png" alt="meshmon Dashboard" width="800">
</p>

### Network Graph Visualization
<p align="center">
  <img src="screenshots/network-graph.png" alt="Network Graph Overview" width="800">
</p>

### Individual Node Details
<p align="center">
  <img src="screenshots/network-graph-node.png" alt="Network Graph Node Detail" width="800">
</p>

### Networks Management
<p align="center">
  <img src="screenshots/network-tab.png" alt="Networks Tab" width="800">
</p>

## How It Works

1. **Node Initialisation**: Each node loads its configuration and generates/loads cryptographic keys
2. **Network Joining**: Nodes join one or more monitoring networks based on configuration
3. **Mutual Monitoring**: Nodes exchange signed health and status information with peers
4. **Verification**: All data is cryptographically verified to ensure authenticity

## Quick Start

### Prerequisites

- **Docker**
- **Docker Compose** (recommended)

### Docker Deployment

1. **Create configuration directory:**
   ```bash
   mkdir config
   ```

2. **Create node configuration:**
   ```bash
   cat > config/nodeconf.yml << EOF
   networks:
     - directory: my-network
       node_id: my-node
   EOF
   ```

3. **Run with Docker:**
   ```bash
   docker run -p 8000:8000 -v ./config:/app/config ghcr.io/ripplefcl/meshmon:latest
   ```

4. **Or use Docker Compose:**
   ```yaml
   # docker-compose.yml
   services:
     meshmon:
       image: ghcr.io/ripplefcl/meshmon:latest
       ports:
         - "8000:8000"
       volumes:
         - ./config:/app/config
       restart: unless-stopped
   ```

   ```bash
   docker-compose up -d
   ```


### Environment Variables

| Variable           | Description                         | Default        |
|--------------------|-------------------------------------|----------------|
| `LOG_LEVEL`        | Set the logging level               | `INFO`         |
| `CONFIG_FILE_NAME` | Name of the node configuration file | `nodeconf.yml` |

## Configuration

### Node Configuration

Inside the config directory, meshmon will look for a `nodeconf.yml`. This contains configuration specific to the individual node.

**Example `nodeconf.yml`:**
```yaml
networks:
  - directory: my-network
    node_id: my-node
    # config_type: git
    # git_repo: https://github.com/your-org/meshmon-configs.git
    # discord_webhook: ...
```

**Configuration Options:**

- **`networks`** (required): Array of networks this node should join
  - **`directory`** (required): Name of the monitoring network directory
  - **`node_id`** (required): Unique identifier for this node within the network
  - **`config_type`** (optional): Configuration source type
    - `local` (default): Use local configuration files
    - `git`: Load configuration from a Git repository
  - **`git_repo`** (optional): Git repository URL when using `config_type: git`
    - Example: `https://github.com/gituser/repo.git`
  - **`discord_webhook`**: (optional) Discord Webhook url to send node status changes too

### Network Configuration

The network config outlined in this section must be present on all nodes. There are two types of network config: `local` or `git`.

#### Configuration Modes

**1. Local Mode (Default)**
- If no folder exists for the network, meshmon will create an example network directory structure in `config/networks/`
- After generation, you need to edit `config/networks/<directory>/config.yml`
- Generated Public keys are automatically placed in the local `pubkeys/` directory

**2. Git Mode**
- If no folder exists locally, it is pulled from Git
- A background task periodically syncs configuration from the remote repository
- Generated Public keys are placed in `config/.public_keys/<network_name>/<node_id>.pub` (since meshmon cannot edit the remote config)


#### Discord Webhook

If multiple nodes share the same webhook the network will elect a leader. only the leader will be allowed to send notifications. the network will also gracefully handle leader failure and re-election.
For webhooks to work you need >= 2 alive nodes in the cluster. this is due to the cluster needing to agree on which nodes are online or offline. the cluster cannot agree with one node.


#### Network Directory Structure

```
config/networks/<directory>/
├── config.yml              # Network configuration
└── pubkeys/                 # Public keys directory
    ├── <node1_id>.pub       # Node public keys
    └── <node2_id>.pub
```


#### Network Config File

The network configuration file `config/networks/<network-name>/config.yml` defines the network topology and node information for monitoring.

**Example `config.yml`:**
```yaml
network_id: test
node_config:
  - node_id: server-01
    url: https://server-01.example.com:8000
  - node_id: server-02
    url: https://server-02.example.com:8000
  - node_id: server-03
    url: https://server-03.example.com:8000
```

**Configuration Options:**

- **`network_id`** (required): Unique identifier for the monitoring network
  - Must be identical on all nodes in the network

- **`node_config`** (required): Array of all nodes participating in this network
  - **`node_id`** (required): Unique identifier for each node within the network
    - Must match the `node_id` specified in the node's `nodeconf.yml`
  - **`url`** (required): Full URL where the node's meshmon instance can be reached
    - Format: `https://hostname:port` or `http://hostname:port`

**Important Notes:**
- Each node in the network will monitor all other nodes listed in `node_config`
- URLs must be accessible from all other nodes in the network
- When first generated, URLs will be set to `replace_me` and need manual configuration


#### Git Repository Structure

When using `config_type: git`, meshmon expects a specific repository structure to manage network configurations centrally.

**Repository Structure:**
```
your-meshmon-configs/
├── config.yml          # Network configuration
├── pubkeys/            # Public keys directory
│   ├── node1.pub      # Node public keys
│   ├── node2.pub
│   └── node3.pub
└── README.md          # Documentation (optional)
```

**File Descriptions:**

- **`config.yml`** (required): The network configuration file
  - Must be identical to what would be in `config/networks/<directory>/config.yml`

- **`pubkeys/`** (required): Directory containing public keys for all nodes in the network
  - **`<node_id>.pub`**: Ed25519 public key file for each node
  - File names must match the `node_id` values in the config.yml
  - Keys are used for cryptographic verification of node communications

**Git Workflow:**
1. Nodes clone the repository on startup when using `config_type: git`
2. Background tasks periodically pull updates from the repository
3. Public keys and network topology are automatically synchronized
4. Configuration changes are distributed to all nodes automatically

---

## Public Cluster

There is a public meshmon cluster you can join. For extra information, read [public_cluster.md](public_cluster.md)

## API Documentation

Once running, visit the **Swagger UI** at `/docs`
