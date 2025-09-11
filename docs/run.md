# Running distomon

This guide explains how to run the distomon distributed monitoring system in different environments.

## Prerequisites
- Python 3.8+
- [Poetry](https://python-poetry.org/)
- Docker (optional)

## Running Locally

1. **Install dependencies:**
   ```bash
   poetry install
   ```
3. **Run the server with Uvicorn:**
   (Recommended for production or advanced local testing)
   ```bash
   poetry run uvicorn src.server:app --host 0.0.0.0 --port 8000
   ```
   - The `--reload` flag enables auto-reload on code changes (useful for development).
   - Adjust `--host` and `--port` as needed.

## Running with Docker

1. **Build and start the service:**
    ```bash
    docker compose up --build
    ```
2. **Stop the service:**
    ```bash
    docker compose down
    ```

The Docker Compose file (`compose.yml`) mounts your local `conf` directory to `/app/src/config` in the container and sets the `CONFIG_FILE_NAME` environment variable. Example service:

```yaml
services:
   node:
      image: ghcr.io/ripplefcl/distomon:latest
      ports:
         - 8000:8000
      environment:
         CONFIG_FILE_NAME: nodeconf.yml
      volumes:
         - ./conf:/app/src/config
      restart: unless-stopped
```

## Configuration

- The main configuration file is `nodeconf.yml` (or as set by the `CONFIG_FILE_NAME` environment variable).
- When running with Docker, place your `nodeconf.yml` in a local `conf/` directory (relative to your project root). This will be mounted into the container at `/app/src/config/nodeconf.yml`.
- Example `nodeconf.yml`:

```yaml
networks:
   - name: test
      node_id: seeg
      config_type: github
      git_repo: https://github.com/rippleFCL/distmon-test.git
login_password: password
```

- You can set environment variables to control logging and config file selection:
   - `LOG_LEVEL` (default: INFO)
   - `CONFIG_FILE_NAME` (default: nodeconf.yml)

## Useful Commands
- **Update dependencies:**
  ```bash
  poetry update
  ```
- **Run linting:**
  ```bash
  poetry run ruff src/
  ```

## Troubleshooting
- Ensure all dependencies are installed and the correct Python version is used.
- Check logs for errors (log level can be set with `LOG_LEVEL`).
- For Docker issues, ensure Docker is running and you have permission to use it.

## Support
For questions or support, open an issue on GitHub.
