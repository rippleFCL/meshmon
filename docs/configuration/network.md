# Network Configuration

Network configuration files live under `config/networks/<directory>/config.yml`

## Important Notes

MeshMon requires that network configuration matches across all nodes in the cluster. Divergence can destabilize or crash the cluster.

Cluster timing parameters are advanced knobs. Changing values in [Cluster](#cluster) can lead to instability; in most cases they shouldn’t be modified.

Also ensure your local `node_id` exists in `node_config[]`, and that peer `url` values are reachable from other nodes. Invalid or inconsistent entries can cause a network to be skipped or peers to be marked offline.

## Root Config

This is the top-level shape of `config.yml`. Only `network_id` and `node_config[]` are required; the other sections are optional and have safe defaults. Each key below links to its detailed section.

| Section          | Description                                                            | Default                          |
| ---------------- | ---------------------------------------------------------------------- | -------------------------------- |
| `network_id`     | The Network id and name                                                | —                                |
| `node_config[]`  | [Node Configuration](#node-list-node_config)                           | —                                |
| `monitors[]`     | [Monitor Configuration](#monitors)                                     | `[]`                             |
| `rebroadcasts[]` | [Rebroadcasting Monitors](#rebroadcasting-monitors-rebroadcasts)       | `[]`                             |
| `cluster`        | [Cluster Configuration](#cluster)                                      | See [Cluster](#cluster) defaults |
| `defaults`       | [Defaults Configuration](#defaults)                                    | See [Defaults](#defaults)        |
| `node_version[]` | [Version Constraints Configuration](#version-constraints-node_version) | `[]`                             |

## Node List (node_config)

Defines all peers and how your node interacts with them.

Section: `node_config[]`

| Field       | Type               | Default                  | What it does                                                                                                        |
| ----------- | ------------------ | ------------------------ | ------------------------------------------------------------------------------------------------------------------- |
| `node_id`   | string (lowercase) | —                        | Peer ID. Your local `node_id` (from nodeconf.yml) must appear here or the network is skipped.                       |
| `url`       | string (optional)  | -                        | gRPC URL peers use to dial this node. Prefer `grpc://` or `grpcs://`. If omitted/empty, peers won’t dial this node. |
| `poll_rate` | int                | defaults.nodes.poll_rate | Heartbeat interval (seconds) for this peer.                                                                         |
| `retry`     | int                | defaults.nodes.retry     | Missed-heartbeat tolerance. Effective timeout ≈ `poll_rate * retry`.                                                |
| `allow`     | list[string]       | []                       | Whitelist: only listed nodes will attempt to connect to this peer (evaluated by the dialling node).                 |
| `block`     | list[string]       | []                       | Blacklist: listed nodes will not connect to this peer (evaluated by the dialling node).                             |

Example (basic):
```yaml
node_config:
  - node_id: node
    url: node:42069
    block:
      - node3
  - node_id: node2
    url: node2:42069
  - node_id: node3
    url: node3:42069
    block:
      - node
```

Example (with optional url):
```yaml
node_config:
  - node_id: edge-node
    # No inbound gRPC on this node
    url: null
```

### Rebroadcasting monitors (rebroadcasts)

Rebroadcasts let you import selected monitor data from another network and publish it under this network’s namespace. This is useful for aggregation or cross-publishing public checks.

Section: `rebroadcasts[]` (root-level)

Each entry defines a rule applied to specific nodes via `apply_to`. For each source monitor that matches the filters, a corresponding destination monitor identity is created in this network using optional prefixes and rewrite rules.

Fields on `rebroadcasts[]` items:

| Field                | Type                         | Default | What it does                                                                                                                                                   |
| -------------------- | ---------------------------- | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apply_to[]`         | list[string]                 | —       | Node IDs (from `node_config[]`) this rule applies to. Only these nodes will rebroadcast the selected data.                                                     |
| `src_net`            | string                       | —       | Source network ID to pull monitor results from.                                                                                                                |
| `monitor_prefix`     | string                       | ""      | Optional prefix applied to destination monitor names before rewrites. If a monitor rewrite matches, it will overwrite the name.                                |
| `group_prefix`       | string                       | ""      | Optional prefix applied to destination groups before rewrites. If a (group or monitor) rewrite sets a destination group, it will overwrite the prefixed value. |
| `groups[]`           | list[string]                 | []      | If provided, only source monitors whose `group` is in this list are considered.                                                                                |
| `monitors[]`         | list[RebroadcastMonitorItem] | []      | Optional explicit allow-list of source monitors to include. If empty, all matching by `groups[]` are used.                                                     |
| `group_rewrites[]`   | list[GroupRewrite]           | []      | Rewrite a source group to a different destination group.                                                                                                       |
| `monitor_rewrites[]` | list[MonitorRewrite]         | []      | Rewrite specific monitor names (and optionally groups) to new destination names and/or groups.                                                                 |

`RebroadcastMonitorItem` shape (entries in `monitors[]`):

| Field   | Type              | Default | What it does                                                    |
| ------- | ----------------- | ------- | --------------------------------------------------------------- |
| `name`  | string            | —       | Source monitor name on `src_net`.                               |
| `group` | string (optional) | null    | If set, match only when the source monitor’s group equals this. |

`GroupRewrite` shape (entries in `group_rewrites[]`):

| Field        | Type   | What it does                                 |
| ------------ | ------ | -------------------------------------------- |
| `src_group`  | string | When the source monitor group equals this... |
| `dest_group` | string | ...rewrite the destination group to this.    |

`MonitorRewrite` shape (entries in `monitor_rewrites[]`):

| Field          | Type              | What it does                                                                                   |
| -------------- | ----------------- | ---------------------------------------------------------------------------------------------- |
| `src_monitor`  | string            | Match source monitor by name.                                                                  |
| `dest_monitor` | string            | Destination monitor name to use.                                                               |
| `src_group`    | string (optional) | If provided, only match when the source group equals this value.                               |
| `dest_group`   | string (optional) | If provided, also rewrite the destination group; otherwise keep the current destination group. |

Order of operations for destination identity (first-match wins for rewrites):

1) Start with `dest_name = src_monitor.name`, `dest_group = src_monitor.group`.
2) Apply `monitor_prefix` and `group_prefix` if set.
3) Apply the first matching `group_rewrite` (matches against the SOURCE group, not the prefixed/destination group).
4) Apply the first matching `monitor_rewrite` (matches against the SOURCE name and optionally SOURCE group) — this can override both destination name and group.

Notes:
- If `monitors[]` is non-empty, only listed monitors are considered (optionally narrowed by `group`).
- If `groups[]` is non-empty, only monitors whose source group is in the list are considered.
- Monitor identity is the pair `group:name`. Changing group or name creates a new identity in this network.
- Prefixes are applied first, but any matching rewrite will overwrite the prefixed value for that field.

Example:

```yaml
rebroadcasts:
  - apply_to: [aggregator]
    src_net: public-net
    # Prefix all rebroadcasted monitors and groups
    monitor_prefix: public-
    group_prefix: ext-
    # Only include these source groups
    groups: [public, core]
    # Include only these monitors (optional filter)
    monitors:
      - name: homepage
      - name: api
        group: public
    # Rewrite groups and specific monitor names
    group_rewrites:
      - src_group: public
        dest_group: external
    monitor_rewrites:
      - src_monitor: api
        src_group: public
        dest_monitor: public-api
```


## Monitors

Configure external HTTP or ping checks that each node runs locally. Use `interval` and `retry` to balance sensitivity vs. noise, and `allow`/`block` to target which nodes run a given monitor.

Section: `monitors[]`

| Field Name | Type                 | Default Value              | What it does                                                                                     |
| ---------- | -------------------- | -------------------------- | ------------------------------------------------------------------------------------------------ |
| `name`     | string               | —                          | Unique monitor name.                                                                             |
| `type`     | enum: `ping`\|`http` | —                          | Monitor implementation.                                                                          |
| `host`     | string               | —                          | Target host/URL the monitor checks.                                                              |
| `group`    | string               | `"default"`                | Logical group/bucket for the monitor. Part of identity and used by rebroadcast filters/rewrites. |
| `interval` | int                  | defaults.monitors.interval | Seconds between checks.                                                                          |
| `retry`    | int                  | defaults.monitors.retry    | Consecutive failures before marking OFFLINE.                                                     |
| `allow`    | list[string]         | []                         | Only these nodes run the monitor locally.                                                        |
| `block`    | list[string]         | []                         | These nodes do not run the monitor locally.                                                      |

Example:
```yaml
monitors:
  - name: example.com
    type: http
    host: http://example.com
    group: public
  - name: cloudflare
    type: ping
    host: 1.1.1.1
    group: core
```

## Cluster

Controls internal timing and rate limiting that coordinate background tasks and state propagation. `rate_limits.update` governs user data propagation; `rate_limits.priority_update` governs system tables (leader election, clock table, node status). `clock_pulse_interval` sets the clock pulse period used to measure propagation delay and clock deltas. Always ensure `rate_limits.priority_update < clock_pulse_interval`.

For deeper guidance (including offline detection formula and tuning tips), see Advanced Tuning: [Cluster Timing and Propagation](advanced/propagation-tuning.md).

Section: `cluster`

| Field                         | Type  | Default | What it does                                                                 |
| ----------------------------- | ----- | ------- | ---------------------------------------------------------------------------- |
| `rate_limits.update`          | float | 5       | Base propagation/update rate limit window.                                   |
| `rate_limits.priority_update` | float | 1       | Priority window; governs system tables (e.g., leader election, clock table). |
| `clock_pulse_interval`        | float | 10      | Interval (seconds) for cluster clock pulses.                                 |
| `avg_clock_pulses`            | int   | 30      | Rolling window (in pulses) for averaging in pulsewave.                       |

Example:
```yaml
cluster:
  rate_limits:
    priority_update: 0.5
  clock_pulse_interval: 10
  avg_clock_pulses: 20
```

## Defaults

Network-wide fallbacks used when individual node or monitor entries omit fields. Tuning these changes the baseline for the whole network without editing every entry.

Section: `defaults`

| Field               | Type | Default | What it does                                        |
| ------------------- | ---- | ------- | --------------------------------------------------- |
| `nodes.poll_rate`   | int  | 120     | Default heartbeat interval for nodes.               |
| `nodes.retry`       | int  | 3       | Default tolerated missed heartbeats before OFFLINE. |
| `monitors.interval` | int  | 120     | Default monitor polling interval.                   |
| `monitors.retry`    | int  | 3       | Default monitor retry threshold before OFFLINE.     |

Example:
```yaml
defaults:
  nodes:
    poll_rate: 10
    retry: 6
  monitors:
    interval: 30
    retry: 2
```

## Version Constraints (node_version)

Optional SemVer constraints for allowed node versions in this network. Use this to roll networks forward/backward safely by admitting only compatible node versions.

- If any constraint does not match the running node version, the network is skipped and a warning is logged.
- Example values: [">=3.0.0", "<4.0.0"]

Example:
```yaml
node_version:
  - ">=3.0.0"
  - "<4.0.0"
```

## Full Example

A complete but minimal example combining all sections:

```yaml
network_id: local
node_config:
  - node_id: node
    url: node:42069
    block:
      - node3
  - node_id: node2
    url: node2:42069
  - node_id: node3
    url: node3:42069
    block:
      - node
  - node_id: aggregator
    url: null

rebroadcasts:
  - apply_to: [aggregator]
    src_net: public
    monitor_prefix: public-
    group_prefix: ext-
    groups: [public]
    monitors:
      - name: google
      - name: github

defaults:
  nodes:
    poll_rate: 120
    retry: 3

cluster:
  rate_limits:
    update: 5

monitors:
  - name: example
    type: http
    host: http://example.com/
  - name: facebook
    type: http
    host: https://www.facebook.com/
  - name: google
    type: http
    host: https://www.google.com/
  - name: github
    type: http
    host: https://www.github.com/
    allow:
      - node
node_version:
  - ">=3.0.0"
  - "<4.0.0"
```
