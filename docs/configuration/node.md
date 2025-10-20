# Node Configuration

The node configuration file `config/nodeconf.yml` defines which networks this node joins.


## Fields
The fields live under `networks[]`

| Field           | Type               | Default | What it does                                                                                                                         |
| --------------- | ------------------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| directory       | string             | —       | Directory under `config/networks/` used to locate `config.yml` and keys.                                                             |
| node_id         | string (lowercase) | —       | Your node's ID inside this network. Must appear in the network's `node_config` or the network is skipped.                            |
| config_type     | enum:  `git`       | `local` | Where to load config/keys from. `local`: uses `config/networks/<directory>/`.  `git`: clones/updates `git_repo` into that directory. |
| git_repo        | string             | null    | Git URL used when `config_type=git`. On pull failure, repo will be recloned on next load.                                            |
| discord_webhook | map[name→url]      | null    | If set, MeshMon posts node/monitor status transitions to these webhooks once the cluster is consistent.                              |


## Discord Webhooks and Notification Clusters

You can enable notifications per network by adding a `discord_webhook` map to that network’s entry in `nodeconf.yml`. The key is a human-friendly name, and the value is the Discord webhook URL.

### Notification Cluster
A notification cluster is formed when the same webhook (sharing a name and value) is used by two or more nodes on the same network. MeshMon will select a leader to emit the notification. This stops single points of failures and duplicated notifications.


## Example
Example (in `config/nodeconf.yml`):

```yaml
networks:
  - directory: local-test
    node_id: node1
    config_type: local        # default: local; alternatives: git
    git_repo: null            # required only when config_type: git
    discord_webhook:          # optional; map of name -> webhook URL
      infra-alerts: https://discord.com/api/webhooks/xxx/yyy
  - directory: meshmon-public-network
    node_id: observer
    config_type: git
    git_repo: https://github.com/your-org/meshmon-public-network
```
