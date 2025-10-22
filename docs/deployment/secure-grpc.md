# Secure gRPC with NGINX (TLS)

This guide shows how to front MeshMon’s gRPC port with TLS using NGINX. It covers two patterns:

- Ingress TLS termination (simple): clients speak TLS to NGINX; NGINX forwards cleartext gRPC to MeshMon.
- Dual-proxy (end‑to‑end over untrusted networks): add a local egress proxy on the caller and a remote ingress proxy on the callee to carry TLS between sites without changing MeshMon.

> Important
> Today MeshMon runs gRPC without TLS (the server adds insecure ports and the client uses an insecure channel). These patterns secure the network path using proxies while MeshMon continues to speak cleartext on localhost. For true in‑process TLS, native support must be added to MeshMon.

## Ports recap

- MeshMon gRPC server listens on: 0.0.0.0:42069 (IPv4) and [::]:42069 (IPv6)
- Your NGINX will typically listen on: 443 (TLS) for inbound

## Option A — Ingress TLS termination (single NGINX)

Use this when the caller can speak TLS (not MeshMon’s built‑in client). NGINX terminates TLS and proxies gRPC to MeshMon on localhost.

nginx.conf (essential bits):

```nginx
http {
  upstream meshmon_grpc {
    server meshmon:42069;   # MeshMon gRPC backend
  }

  server {
    listen 42069 ssl http2;
    server_name grpc.example.com;

    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    # Optional: strong TLS
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
      grpc_pass grpc://meshmon_grpc;

      grpc_set_header TE trailers;
      grpc_set_header Host $host;

      # MeshMon uses server-nonce/client-nonce for mutual auth during handshake:
      # - client-nonce is sent by the client; NGINX forwards it automatically.
      # - server-nonce is sent by the upstream; add pass_header so clients see it.
      grpc_pass_header server-nonce;

      # Optional headers/limits
      grpc_read_timeout  300s;
      grpc_send_timeout  300s;
    }
  }
}
```

Docker compose example:

```yaml
services:
  meshmon:
    image: ghcr.io/ripplefcl/meshmon:latest
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config

  nginx:
    image: nginx:stable
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    ports:
      - "42069:42069"
    depends_on:
      - meshmon
```

## Troubleshooting

- UNAVAILABLE or HTTP/1.1 errors: ensure `http2` is enabled on the `listen` directives and you are using `grpc_pass`.
- Handshake failures: verify cert chain, SNI (`grpc_set_header Host`), and CA trust settings.
- Timeouts: increase `grpc_read_timeout`/`grpc_send_timeout`; ensure upstream 42069 is reachable from ingress.
