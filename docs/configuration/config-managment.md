# Configuration Management

This page outlines the supported ways to manage MeshMon configuration and keys, plus recommended workflows and trade‑offs.

## Overview

Configuration is split into two layers:

- Node config (`config/nodeconf.yml`): which networks this node joins and per-node options (e.g., `discord_webhook`).
- Network config (`config/networks/<directory>/config.yml`): the network’s topology, defaults, monitors, and cluster timings.

## Network config file structure

A configuration for each network

Network configurations are stored in `config/networks`. Each network's configuration exists within a subdirectory (named per `networks[].directory`). Each subdirectory must have the following structure:

```
config.yml         # Network configuration (YAML)
pubkeys/           # Public keys for peers in this network
    <node_id>.pub  # One file per peer; filename must match node_id
```

- `config.yml` — See full field reference: [Network Configuration](./network.md)

- `pubkeys/` — Contains a `<node_id>.pub` file for each peer listed in `node_config[]`. A network will not load unless a verifier exists for every peer.

## Options

### 1. Local (per-node filesystem)

- Set `config_type: local` in `nodeconf.yml` (default).
- MeshMon ensures `config/networks/<directory>/` exists and will write a minimal `config.yml` if missing.
- You maintain `config.yml` and `pubkeys/` locally on each node.

Pros:

- Simple to get started; no external dependencies.
- Full local control per node.

Cons:

- Manual sync across nodes (risk of drift).

### 2. Git (centralised repository)

- Set `config_type: git` and provide `git_repo` in `nodeconf.yml`.
- MeshMon clones/updates the repository into `config/networks/<directory>/`.
- Only one network configuration can exist per repository.
- On failure to pull, the local clone is removed; it will be cloned on next load.


!!! note "Public Keys"
    For git configs, your node’s public key is written to `config/.public_keys/<directory>/` (not in the repository). Share it with repo maintainers to add under `pubkeys/` in the repository.

!!! danger "Private Keys"
    Do not commit private keys (`config/.private_keys/`).

Pros:

- Versioned, auditable source of truth.
- Easy rollouts.
- Multi-node sync via Git instead of manual copies.

Cons:

- Operational dependency on the Git host.

## Keys and Verification

- MeshMon must have a verifier for every peer in `node_config[]`. Place files as `config/networks/<directory>/pubkeys/<node_id>.pub`.
- This node’s public key is saved automatically:
    - Local configs: into `config/networks/<directory>/pubkeys/`
    - Git configs: into `config/.public_keys/<directory>/` (not in the repo). Share this file with repo maintainers to add to `pubkeys/`.
- This node's private key is saved automatically into `config/.private_keys/<directory>/`

If a verifier is missing for any `node_id`, the network will fail to validate and won’t be loaded.

## Reloads and Lifecycle

MeshMon hot reloads on config changes.

- Local changes: MeshMon tracks file mtimes under `config/networks/` and `nodeconf.yml` to detect changes.
- Git changes: MeshMon periodically checks for updates and pulls the repo. On pull failure, the local clone is removed; it will be cloned on next load.
- Node membership: `node_id` must be present in the network’s `node_config` or the network is skipped.

## Suggested Workflows

- Local testing: start with `local`, auto-scaffold a minimal `config.yml`, and manually copy pubkeys.
- Staging/production: switch to `git` with a dedicated config repo. PRs add nodes and their pubkeys, adjust monitors and cluster timings, and use tags for controlled rollouts.

## Troubleshooting

- “Network Configuration Missing”: `config/networks/<directory>/config.yml` not found.
- “Node ID Missing”: your `node_id` isn’t listed under `node_config[]`.
- “Verifier Load Error”: missing or malformed `pubkeys/<node_id>.pub`.
- Cluster not converging: ensure pubkeys and URLs are correct. As a last resort verify clocks/ratelimits in [Advanced Tuning](advanced/propagation-tuning.md)
