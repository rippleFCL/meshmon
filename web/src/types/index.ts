// New simplified API types (from OpenAPI)
// These mirror the backend /api/view response and are adapted to legacy shapes for the UI
export type NodeStatusEnum = 'online' | 'offline' | 'unknown'
export type MonitorStatusEnum = 'up' | 'down' | 'unknown'
export type ConnectionType = 'up' | 'down' | 'unknown'

export interface MeshMonApi {
  networks: { [networkId: string]: NetworkInfoNew }
}

export interface NetworkInfoNew {
  nodes: { [nodeId: string]: NodeInfoNew }
  connections: ConnectionInfo[]
  monitors: MonitorInfo[]
  monitor_connections: MonitorConnectionInfo[]
}

export interface NodeInfoNew {
  node_id: string
  status: NodeStatusEnum
  version: string
}

export interface ConnectionNodeInfo {
  rtt: number
  name: string
  conn_type: ConnectionType
}

export interface ConnectionInfo {
  src_node: ConnectionNodeInfo
  dest_node: ConnectionNodeInfo
}

export interface MonitorInfo {
  monitor_id: string
  name: string
  group: string
  status: MonitorStatusEnum
}

export interface MonitorConnectionInfo {
  node_id: string
  monitor_id: string
  status: MonitorStatusEnum
  rtt: number
}

// API Response Types from the actual /view endpoint
export interface MultiNetworkAnalysis {
  networks: {
    [networkId: string]: NetworkAnalysis
  }
}

export interface NetworkAnalysis {
  total_nodes: number
  online_nodes: number
  offline_nodes: number
  node_analyses: {
    [nodeId: string]: NodeAnalysis
  }
  monitor_analyses: {
    [monitorId: string]: MonitorAnalysis
  }
}

export interface NodeAnalysis {
  node_status: 'online' | 'offline'
  inbound_info: {
    [nodeId: string]: NodeConnectionDetail
  }
  outbound_info: {
    [nodeId: string]: NodeConnectionDetail
  }
  inbound_status: AggregatedConnectionDetail
  outbound_status: AggregatedConnectionDetail
  node_info: NodeInfo
}

export interface NodeInfo {
  version: string
  data_retention: string
}

export interface NodeConnectionDetail {
  status: 'online' | 'offline' | 'unknown' | 'node_down'
  rtt: number
}

export interface AggregatedConnectionDetail {
  total_connections: number
  online_connections: number
  offline_connections: number
  average_rtt: number
  status: 'online' | 'degraded' | 'offline'
}

export interface MonitorDetail {
  status: 'online' | 'offline' | 'unknown' | 'node_down'
  rtt: number
}

export interface MonitorAnalysis {
  monitor_status: 'online' | 'offline' | 'unknown'
  inbound_info: {
    [nodeId: string]: MonitorDetail
  }
  inbound_status: AggregatedConnectionDetail
}

// Legacy ViewResponse for backward compatibility
export interface ViewResponse extends MultiNetworkAnalysis {}

export interface ViewNetwork {
  data: {
    [nodeId: string]: ViewNodeData
  }
}

export interface ViewNodeData {
  ping_data: {
    [targetNodeId: string]: ViewPingData
  }
  node_version: string
}

export interface ViewPingData {
  status: 'online' | 'offline' | 'unknown'
  response_time: number
  response_time_rtt: number
}

// Legacy types (keeping for backward compatibility)
export interface ApiResponse<T> {
  data: T
  message?: string
  success: boolean
}

// Network Types
export interface Network {
  id: string
  name: string
  description?: string
  status: 'online' | 'offline' | 'warning'
  nodeCount: number
  createdAt: string
  updatedAt: string
}

// Node Types
export interface Node {
  id: string
  networkId: string
  url: string
  status: 'online' | 'offline' | 'warning'
  lastSeen: string
  latency?: number
  publicKey?: string
}

// Monitoring Types
export interface PingData {
  nodeId: string
  networkId: string
  timestamp: string
  latency: number
  success: boolean
}

export interface NetworkStats {
  totalNetworks: number
  totalNodes: number
  avgLatency: number
  alertCount: number
}

// Activity Types
export interface Activity {
  id: string
  type: 'node_connected' | 'node_disconnected' | 'high_latency' | 'network_scan'
  message: string
  timestamp: string
  severity: 'info' | 'warning' | 'error'
}

// Settings Types
export interface Settings {
  refreshInterval: number
  alertThreshold: number
  logLevel: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR'
}
