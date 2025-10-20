# MeshMon Documentation

MeshMon: a distributed peer-to-peer monitoring system.

## What is MeshMon?

MeshMon monitors services from multiple vantage points and reaches a cluster-wide consensus on their status without relying on a single central coordinator. Each node:

- Runs local checks (HTTP, pings, etc.) and publishes results to peers
- Exchanges signed state with other nodes over a lightweight mesh
- Uses a clock table and leader election to coordinate propagation and resolve disagreements

Why this design:

- Resilience: no single control-plane to fail; nodes can join/leave with minimal impact
- Trust: signatures and version gates prevent untrusted peers from poisoning the cluster
- Real-world signal: monitoring from different networks avoids false positives from a single observer

Key concepts:

- Networks: logical groups of nodes that share a config (`config/networks/<id>/config.yml`)
- Node config: which networks to join and optional webhooks per node
- Monitors: HTTP/ping checks run by specific nodes, with allow/block targeting
- Status convergence: nodes exchange evidence until the cluster agrees; webhooks trigger once consensus is reached

## Getting Started

- [Quick Start Guide](quick-start.md)
- Configuration: Define per-node and per-network behaviour.
    - [Node Configuration](configuration/node.md) — which networks to join, webhooks, and runtime knobs.
    - [Network Configuration](configuration/network.md) — topology, monitors, cluster timings, and defaults.
    - [Config Management](configuration/config-managment.md) — local vs Git-based workflows and keys.
