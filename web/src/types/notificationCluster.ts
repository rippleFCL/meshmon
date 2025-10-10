// Types matching backend /api/notification_cluster

export type NotificationClusterStatusEnum =
  | 'LEADER'
  | 'FOLLOWER'
  | 'WAITING_FOR_CONSENSUS'
  | 'NOT_PARTICIPATING'

export interface NotificationCluster {
  // key: node_id
  node_statuses: Record<string, NotificationClusterStatusEnum>
}

export interface NotificationClusters {
  // key: cluster name (e.g., channel or integration name)
  clusters: Record<string, NotificationCluster>
}

export interface NotificationClusterApi {
  // key: network id
  networks: Record<string, NotificationClusters>
}
