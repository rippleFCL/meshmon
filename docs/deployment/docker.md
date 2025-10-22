# Docker Deployment

This guide explains how to run MeshMon using the official Docker image, how to mount configuration and keys, what ports are exposed, and how to perform updates.

## Image and entrypoint

- Image: `ghcr.io/ripplefcl/meshmon:latest`
- Entrypoint: `uvicorn server:api`
- Default host/port: `0.0.0.0:8000`

## Ports

- 8000/tcp — Web UI and API (Uvicorn)
- 42069/tcp — gRPC peer port (exposed by application; map as needed in compose)

## Volumes and configuration

The container expects a `config/` directory mounted at `/app/config`:

- `/app/config/nodeconf.yml` — node configuration (which networks to join, webhooks, etc.)
- `/app/config/networks/<directory>/config.yml` — per-network topology and defaults
- `/app/config/networks/<directory>/pubkeys/` — public keys (`<node_id>.pub`) for peers in the network
- `/app/.private_keys/<directory>/` — created automatically for the container’s node private key
- `/app/.public_keys/<directory>/` — created automatically for this node’s public key when using git-based configs

Recommended host layout:

```
meshmon/
  config/
    nodeconf.yml
    networks/
      local/
        config.yml
        pubkeys/
          node-1.pub
          node-2.pub
          node-3.pub
```

Mount with compose:

```yaml
services:
  node:
    image: ghcr.io/ripplefcl/meshmon:latest
    ports:
      - "8000:8000"   # Web UI + API
      - "42069:42069" # gRPC (if reachable from peers)
    volumes:
      - ./config:/app/config
    restart: unless-stopped
```

Or with docker run:

```bash
docker run -d \
  -p 8000:8000 \
  -p 42069:42069 \
  -v $(pwd)/config:/app/config \
  --name meshmon \
  ghcr.io/ripplefcl/meshmon:latest
```

## Environment variables

The container sets sensible defaults via environment variables:

- `UVICORN_HOST` (default `0.0.0.0`) — listen address
- `UVICORN_PORT` (default `8000`) — listen port
- `ENABLE_TELEMETRY` (default `false`) enables sentry crash reporting

To override port, you may also pass `--port` via the command (see Advanced usage below).

