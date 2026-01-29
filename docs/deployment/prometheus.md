# Prometheus Integration

MeshMon exposes a comprehensive set of metrics in Prometheus format, enabling seamless integration with your monitoring and alerting infrastructure. This guide explains how to configure Prometheus to scrape MeshMon metrics, what metrics are available, and how to use them for monitoring and alerting.

## Overview

MeshMon exposes metrics on the `/metrics` endpoint in the standard Prometheus text format. These metrics cover:

- **Node Status**: Online/offline status, RTT, and last-seen timestamps
- **Monitor Health**: Check status, errors, and performance
- **gRPC Transport**: Packets, bytes, and latency across the mesh network
- **Connection Health**: Active connections, establishment/closure rates, and link utilization

All metrics are automatically updated when accessed, with labels for network ID, node ID, and other relevant dimensions.

## Configuration

### Prometheus Scrape Configuration

Add the following to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'meshmon'
    static_configs:
      - targets: ['localhost:8000']  # MeshMon API endpoint
    metrics_path: '/metrics'
    scrape_interval: 15s             # Default Prometheus interval
    scrape_timeout: 10s
```

For multiple MeshMon nodes:

```yaml
scrape_configs:
  - job_name: 'meshmon-cluster'
    static_configs:
      - targets:
          - 'node-1:8000'
          - 'node-2:8000'
          - 'node-3:8000'
    metrics_path: '/metrics'
    scrape_interval: 15s
```

## Available Metrics

### Node Status Metrics

These metrics track the status of individual nodes in your mesh network.

**`meshmon_node_status`** (Gauge)
- Values: `1` (online), `0.5` (unknown), `0` (offline)
- Labels: `network_id`, `node_id`
- Use for: Alerting on node availability, calculating cluster health percentage

```promql
# Check if node is online
meshmon_node_status{network_id="local-network",node_id="node-1"} == 1

# Count online nodes per network
count(meshmon_node_status == 1) by (network_id)

# Calculate cluster availability percentage
(count(meshmon_node_status == 1) by (network_id) / count(meshmon_node_status) by (network_id)) * 100
```

**`meshmon_node_rtt_seconds`** (Gauge)
- Round-trip time to each node in seconds
- Labels: `network_id`, `node_id`
- Use for: Detecting latency issues, alerting on slow peers

```promql
# Alert if RTT exceeds 100ms
meshmon_node_rtt_seconds > 0.1

# Calculate average RTT per network
avg(meshmon_node_rtt_seconds) by (network_id)

# P95 latency
histogram_quantile(0.95, meshmon_node_rtt_seconds) by (network_id)
```

**`meshmon_node_last_seen_timestamp_seconds`** (Gauge)
- Unix timestamp when the node was last seen
- Labels: `network_id`, `node_id`
- Use for: Custom alerting on stale nodes

```promql
# Find nodes not seen in last 5 minutes
(time() - meshmon_node_last_seen_timestamp_seconds) > 300
```

**`meshmon_node`** (Info)
- Static node information
- Labels: `network_id`, `node_id`
- Use for: Enriching alerts and dashboards with node metadata

### Monitor Status Metrics

These metrics track the health of monitors (HTTP checks, pings, etc.).

**`meshmon_monitor_status`** (Gauge)
- Values: `1` (online), `0.5` (unknown), `0` (offline)
- Labels: `network_id`, `monitor_name`, `monitor_type`
- Use for: Alerting on service outages

```promql
# Count failed monitors per network
count(meshmon_monitor_status == 0) by (network_id)

# Alert if any critical monitor is down
meshmon_monitor_status{monitor_type="http"} == 0
```

**`meshmon_monitor_rtt_seconds`** (Gauge)
- Round-trip time to monitor target in seconds
- Labels: `network_id`, `monitor_name`, `monitor_type`
- Use for: Performance monitoring of checked services

```promql
# Calculate average response time per monitor
avg(meshmon_monitor_rtt_seconds) by (monitor_name)

# Detect slow responses
meshmon_monitor_rtt_seconds > 1.0
```

**`meshmon_monitor_errors_total`** (Counter)
- Total number of monitor check errors
- Labels: `network_id`, `monitor_name`, `monitor_type`
- Use for: Tracking check reliability and error patterns

```promql
# Error rate per monitor (errors per minute)
rate(meshmon_monitor_errors_total[1m]) by (monitor_name)

# Alert on error rate increase
rate(meshmon_monitor_errors_total[5m]) > rate(meshmon_monitor_errors_total[1h] offset 1h)
```

**`meshmon_monitor_last_check_timestamp_seconds`** (Gauge)
- Unix timestamp of last monitor check
- Labels: `network_id`, `monitor_name`, `monitor_type`
- Use for: Alerting on stale checks

```promql
# Alert if monitor check hasn't run in 10 minutes
(time() - meshmon_monitor_last_check_timestamp_seconds) > 600
```

### gRPC Transport Metrics

These metrics track communication between mesh nodes.

**`meshmon_grpc_packets_received_total`** (Counter)
- Total packets received
- Labels: `network_id`, `source_node_id`, `packet_type`
- Types: `heartbeat`, `state_sync`, `monitor_sync`, `unknown`

```promql
# Packet rate by type
rate(meshmon_grpc_packets_received_total[1m]) by (packet_type)

# Total packets from a specific node
meshmon_grpc_packets_received_total{source_node_id="node-1"}
```

**`meshmon_grpc_packets_sent_total`** (Counter)
- Total packets sent
- Labels: `network_id`, `dest_node_id`, `packet_type`

```promql
# Compare sent vs received packets
rate(meshmon_grpc_packets_sent_total[1m]) by (dest_node_id)
```

**`meshmon_grpc_bytes_received_total`** (Counter)
- Total bytes received via gRPC
- Labels: `network_id`, `source_node_id`, `packet_type`
- Use for: Bandwidth analysis and capacity planning

```promql
# Bandwidth per node (bytes/sec)
rate(meshmon_grpc_bytes_received_total[1m]) by (source_node_id)

# Total data transferred
meshmon_grpc_bytes_received_total + meshmon_grpc_bytes_sent_total
```

**`meshmon_grpc_bytes_sent_total`** (Counter)
- Total bytes sent via gRPC
- Labels: `network_id`, `dest_node_id`, `packet_type`

**`meshmon_grpc_packet_processing_duration_seconds`** (Histogram)
- Time spent processing packets (with preset buckets)
- Labels: `network_id`, `packet_type`
- Buckets: 0.1ms to 1s
- Use for: Detecting processing bottlenecks

```promql
# P99 packet processing time
histogram_quantile(0.99, meshmon_grpc_packet_processing_duration_seconds) by (packet_type)

# Average processing time
rate(meshmon_grpc_packet_processing_duration_seconds_sum[1m]) / rate(meshmon_grpc_packet_processing_duration_seconds_count[1m]) by (packet_type)
```

### Connection Metrics

These metrics track gRPC connections between mesh nodes.

**`meshmon_grpc_connections_active`** (Gauge)
- Number of active connections
- Labels: `network_id`, `node_id`, `direction` (inbound/outbound)
- Use for: Monitoring connection health

```promql
# Total active connections per network
sum(meshmon_grpc_connections_active) by (network_id)

# Inbound vs outbound balance
meshmon_grpc_connections_active{direction="inbound"} vs meshmon_grpc_connections_active{direction="outbound"}
```

**`meshmon_grpc_connections_established_total`** (Counter)
- Total connections established
- Labels: `network_id`, `node_id`, `initiator`

```promql
# Connection rate
rate(meshmon_grpc_connections_established_total[1m]) by (network_id)
```

**`meshmon_grpc_connections_closed_total`** (Counter)
- Total connections closed
- Labels: `network_id`, `node_id`

**`meshmon_heartbeat_latency_seconds`** (Histogram)
- Latency of heartbeat messages

## Common Alert Rules

Here are recommended alert rules for your `alert.yml`:

```yaml
groups:
  - name: meshmon-alerts
    interval: 30s
    rules:
      # Node availability alerts
      - alert: MeshMonNodeDown
        expr: meshmon_node_status == 0
        for: 2m
        annotations:
          summary: "MeshMon node {{ $labels.node_id }} is down"
          description: "Node {{ $labels.node_id }} in network {{ $labels.network_id }} has been offline for 2 minutes"

      # Cluster health alerts
      - alert: MeshMonClusterDegraded
        expr: (count(meshmon_node_status == 1) by (network_id) / count(meshmon_node_status) by (network_id)) < 0.75
        for: 5m
        annotations:
          summary: "MeshMon cluster {{ $labels.network_id }} health < 75%"

      # High latency alerts
      - alert: MeshMonHighLatency
        expr: meshmon_node_rtt_seconds > 0.5
        for: 5m
        annotations:
          summary: "High latency to {{ $labels.node_id }}"
          description: "RTT to node {{ $labels.node_id }} is {{ $value }}s (threshold: 500ms)"

      # Monitor failure alerts
      - alert: MeshMonMonitorDown
        expr: meshmon_monitor_status == 0
        for: 3m
        annotations:
          summary: "Monitor {{ $labels.monitor_name }} is down"
          description: "Monitor {{ $labels.monitor_name }} ({{ $labels.monitor_type }}) in network {{ $labels.network_id }} is down"

      # Monitor error rate alerts
      - alert: MeshMonMonitorErrorRate
        expr: rate(meshmon_monitor_errors_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "High error rate for monitor {{ $labels.monitor_name }}"
          description: "Error rate for {{ $labels.monitor_name }} is {{ $value }} errors/sec"

      # Stale monitor checks
      - alert: MeshMonStaleChecks
        expr: (time() - meshmon_monitor_last_check_timestamp_seconds) > 600
        for: 1m
        annotations:
          summary: "Monitor {{ $labels.monitor_name }} checks are stale"
          description: "Monitor {{ $labels.monitor_name }} hasn't run a check in 10 minutes"

      # Connection issues
      - alert: MeshMonConnectionDrop
        expr: increase(meshmon_grpc_connections_closed_total[5m]) > 10
        annotations:
          summary: "High connection closure rate on {{ $labels.node_id }}"
          description: "{{ $labels.node_id }} has closed {{ $value }} connections in the last 5 minutes"
```

## Grafana Dashboards

### Example Dashboard JSON

Create a Grafana dashboard to visualize MeshMon metrics. Key panels:

1. **Cluster Health** - Pie chart of node status distribution
   ```promql
   meshmon_node_status
   ```

2. **Node Status Timeline** - Status over time
   ```promql
   meshmon_node_status
   ```

3. **Network Latency** - Line chart of RTT
   ```promql
   meshmon_node_rtt_seconds
   ```

4. **Monitor Status** - Table of all monitors
   ```promql
   meshmon_monitor_status
   ```

5. **Packet Throughput** - Stacked bar chart
   ```promql
   rate(meshmon_grpc_packets_received_total[1m]) by (packet_type)
   ```

6. **Processing Duration** - Histogram visualization
   ```promql
   histogram_quantile(0.95, meshmon_grpc_packet_processing_duration_seconds)
   ```

### Import Pre-built Dashboard

1. Go to Dashboards → Import
2. Enter the dashboard ID or paste JSON
3. Select your Prometheus data source
4. Click Import

## Best Practices

### Scrape Configuration

- **Scrape Interval**: Use 15-30 seconds for normal monitoring, 5 seconds for critical clusters
- **Scrape Timeout**: Set to less than scrape interval (usually 80% of interval)
- **Metric Cardinality**: Be aware that each unique label combination creates a new time series. Limit by node ID or network if you have many targets.

### Alerting

- Start with the provided alert rules and customize thresholds for your environment
- Use `for` clauses to avoid alerting on transient issues
- Include network and node context in alert annotations
- Consider alert dependencies (e.g., suppress monitor alerts if node is down)


Example recording rule:

```yaml
groups:
  - name: meshmon-recording
    interval: 30s
    rules:
      - record: meshmon:node_availability:ratio
        expr: count(meshmon_node_status == 1) / count(meshmon_node_status) by (network_id)

      - record: meshmon:packet_rate:5m
        expr: rate(meshmon_grpc_packets_received_total[5m]) by (network_id, packet_type)
```

## Next Steps

- [Configure Node Webhooks](../configuration/node.md#webhooks) to trigger actions based on metrics
- [Set up Alertmanager](https://prometheus.io/docs/alerting/latest/alertmanager/) for notification routing
- Explore [Prometheus recording rules](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/) for performance optimization
- Create [custom Grafana dashboards](https://grafana.com/docs/grafana/latest/dashboards/) for your use case
