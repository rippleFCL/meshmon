# distomon

**Distributed Monitoring Solution by Ripple**

## Introduction

distomon is a distributed monitoring solution designed to monitor, manage, and analyze distributed systems and services. Built by Ripple, it provides secure, scalable, and extensible monitoring for decentralized networks. The system leverages FastAPI, cryptographic signing, and a modular configuration system to ensure robust and secure operations across distributed nodes.

## How It Works

Each node runs a server that loads its configuration and cryptographic keys, then joins one or more networks. Nodes monitor each other by exchanging signed status and health information. Configuration can be loaded locally or from remote GitHub repositories, and cryptographic verification ensures authenticity of all exchanged data. The system is extensible, allowing for new networks, nodes, and monitoring logic to be added easily.

## Features

- Distributed configuration management (local or GitHub-based)
- Secure cryptographic signing and verification (Ed25519)
- Node health/status monitoring and alerting
- Pluggable monitoring logic per network
- Dockerized deployment for easy scaling
- Password-protected API endpoints
- Logging with configurable log level

## Environment Variables

The following environment variables are supported:

- `LOG_LEVEL`: Set the logging level (default: `INFO`)
- `CONFIG_FILE_NAME`: Name of the node configuration file (default: `nodeconf.yml`)

## Project Structure

```
src/
	server.py         # Main FastAPI server, loads config, starts managers
	test.py           # Test script for configuration and network loading
	distmon/
		config.py       # Configuration loader, supports local/GitHub
		conman.py       # Configuration manager for runtime updates
		crypto.py       # Signing, verification, key management
		distrostore.py  # Distributed storage and node data
		monitor.py      # Monitoring logic and manager
		version.py      # Versioning utilities
```


## Dependencies

Core dependencies (see `pyproject.toml`):

- fastapi
- uvicorn
- pydantic
- pyyaml
- cryptography
- gitpython
- requests
- python-jose[cryptography]
- passlib
- bcrypt
- pre-commit

Dev dependencies:
- ruff

## Ideas for Potential New Features

- **Frontend Client**: Web dashboard for real-time monitoring, configuration, and alerting (coming soon)
- REST API for external integrations
- Automated alerting (email, Slack, etc.)
- Historical data storage and analytics
- Role-based access control and multi-user support
- Support for additional cryptographic algorithms
- Integration with orchestration tools (Kubernetes, Nomad)

## License

MIT License. See [LICENSE](LICENSE) for details.
