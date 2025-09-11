# Distomon

A distributed network monitoring system that tracks health and connectivity across multiple nodes with cryptographic authentication.

## Overview

Distomon enables real-time monitoring of distributed systems by having nodes continuously ping each other and report their findings through a centralized API. Each node runs an instance of the monitoring server, collecting data from other nodes and providing both programmatic and web-based access to network health information.

### Key Features

- **Distributed Architecture**: Each node monitors others and shares data across the network
- **Cryptographic Security**: All node communications are cryptographically signed and verified
- **Real-time Monitoring**: Continuous health checks with configurable polling intervals
- **Web Dashboard**: JWT-authenticated web interface for viewing network status
- **RESTful API**: Programmatic access to monitoring data
- **Multi-network Support**: Monitor multiple isolated networks simultaneously
- **Docker Support**: Easy deployment via Docker containers

## Quick Start

### Prerequisites

- Python 3.13+
- Poetry (for dependency management)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd distomon
```

2. Install dependencies:
```bash
poetry install
```

3. Configure your network (see [Configuration](#configuration))

4. Start the server:
```bash
poetry run python src/server.py
```

### Docker Deployment

For multi-node setup using Docker Compose:

```bash
docker-compose up -d
```

This starts three nodes on ports 8000, 8001, and 8002.

## Configuration

Create a `nodeconf.yml` file in your project root:

```yaml
networks:
  - name: "production-network"
    node_id: "node-1"
    config_type: "local"
login_password: "your-secure-password"
```

Network configuration files define:
- Node lists with URLs and polling rates
- Cryptographic keys for message verification
- Retry policies and timeouts

## API Endpoints

### Authentication
- `POST /token` - Get JWT token (HTTP Basic Auth required)

### Monitoring
- `POST /mon/{network_id}` - Submit monitoring data (requires signature)
- `GET /view/{network_id}` - Get network status (requires JWT)

## Architecture

- **Server** (`src/server.py`): FastAPI web server with authentication and monitoring endpoints
- **Configuration** (`src/distmon/config.py`): Network and node configuration management
- **Data Storage** (`src/distmon/distrostore.py`): Thread-safe storage with cryptographic verification
- **Monitoring** (`src/distmon/monitor.py`): Background monitoring and data collection
- **Cryptography** (`src/distmon/crypto.py`): Message signing and verification

## Development

### Setup
```bash
poetry install
poetry shell
```

### Code Quality
```bash
# Linting and formatting
ruff check --fix
ruff format

# Type checking
pyright

# Run pre-commit hooks
pre-commit run --all-files
```

### Testing
```bash
python src/test.py
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

