// Types matching backend /api/cluster

export type ClusterNodeStatusEnum = 'online' | 'offline' | 'unknown'

export interface ClusterClockTableEntry {
  delta_ms: number
  node_time: string // ISO string from backend
}

export interface ClusterInfo {
  node_statuses: Record<string, ClusterNodeStatusEnum>
  clock_table: Record<string, ClusterClockTableEntry>
}

export interface ClusterInfoApi {
  networks: Record<string, ClusterInfo>
}
