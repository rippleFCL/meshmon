import { MultiNetworkAnalysis, NetworkAnalysis, NodeAnalysis, AggregatedConnectionDetail, MonitorAnalysis, MeshMonApi, MonitorStatusEnum } from '../types'

// Helper to build AggregatedConnectionDetail
const agg = (total: number, online: number, avg: number): AggregatedConnectionDetail => ({
  total_connections: total,
  online_connections: online,
  offline_connections: Math.max(0, total - online),
  average_rtt: avg,
  status: online === total ? 'online' : online > 0 ? 'degraded' : 'offline',
})

// Deterministic mock data for development
const buildMockNetwork = (_id: string, nodesCount = 20, monitorsCount = 40): NetworkAnalysis => {
  // node names: node, node2, node3, ...
  const nodes = Array.from({ length: nodesCount }, (_, i) => (i === 0 ? 'node' : `node${i + 1}`))
  // monitor names: monitor1..monitorN
  const monitors = Array.from({ length: monitorsCount }, (_, i) => `monitor${i + 1}`)

  const node_analyses: Record<string, NodeAnalysis> = {}

  // Define a simple mesh with some variation
  nodes.forEach((nid, idx) => {
    // Make every 6th node offline for some variance
    const online = (idx + 1) % 6 !== 0
    const outbound_info: Record<string, any> = {}
    const inbound_info: Record<string, any> = {}

    nodes.forEach((tid, jdx) => {
      if (tid === nid) return
      // make a sparse ring graph: connect to neighbor indices
      const connected = Math.abs(jdx - idx) === 1 ||
        (idx === 0 && jdx === nodes.length - 1) ||
        (idx === nodes.length - 1 && jdx === 0)
      if (connected) {
        const rtt = 20 + (idx + jdx) * 5
        outbound_info[tid] = { status: online ? 'online' : 'node_down', rtt }
        inbound_info[tid] = { status: online ? 'online' : 'node_down', rtt }
      }
    })

    const totalOut = Object.keys(outbound_info).length
    const totalIn = Object.keys(inbound_info).length
    const avgOut = totalOut ? Math.round(Object.values(outbound_info).reduce((s: number, d: any) => s + d.rtt, 0) / totalOut) : 0
    const avgIn = totalIn ? Math.round(Object.values(inbound_info).reduce((s: number, d: any) => s + d.rtt, 0) / totalIn) : 0
    node_analyses[nid] = {
      node_status: online ? 'online' : 'offline',
      outbound_info,
      inbound_info,
      outbound_status: agg(totalOut, online ? totalOut : 0, avgOut),
      inbound_status: agg(totalIn, online ? totalIn : 0, avgIn),
      node_info: { version: '1.2.3', data_retention: '7d' },
    }
  })

  // Monitors: nodes monitor monitors (inbound_info is per source node)
  const monitor_analyses: Record<string, MonitorAnalysis> = {}
  monitors.forEach((mid, mIdx) => {
    const inbound_info: Record<string, any> = {}
    nodes.forEach((nid, idx) => {
      const nodeOnline = node_analyses[nid].node_status === 'online'
      // Make ~1/3 of nodes monitor this monitor based on modulo pattern
      const participates = (idx + mIdx) % 3 === 0
      if (participates) {
        const rtt = 25 + (idx + mIdx) * 7
        inbound_info[nid] = { status: nodeOnline ? 'online' : 'node_down', rtt }
      }
    })
    const total = Object.keys(inbound_info).length
    const online = Object.values(inbound_info).filter((d: any) => d.status === 'online').length
    const avg = total ? Math.round(Object.values(inbound_info).reduce((s: number, d: any) => s + (d as any).rtt, 0) / total) : 0
    monitor_analyses[mid] = {
      monitor_status: online > 0 ? 'online' : 'unknown',
      inbound_info,
      inbound_status: agg(total, online, avg),
    }
  })

  const total_nodes = nodes.length
  const online_nodes = Object.values(node_analyses).filter(n => n.node_status === 'online').length
  const offline_nodes = total_nodes - online_nodes

  return { total_nodes, online_nodes, offline_nodes, node_analyses, monitor_analyses }
}

export const mockMultiNetworkAnalysis: MultiNetworkAnalysis = {
  networks: {
    'mock-net1': buildMockNetwork('local-test', 20, 50),
    'mock-net2': buildMockNetwork('staging', 3, 10),
    'mock-net3': buildMockNetwork('production', 1, 1),
  },
}

export const mockHealth = { ok: true }

// Map legacy/analysis mock into the new MeshMonApi shape used by the UI
const statusToConnType = (s: string): 'up' | 'down' | 'unknown' => (s === 'online' ? 'up' : s === 'offline' || s === 'node_down' ? 'down' : 'unknown')
const monStatusToEnum = (s: string): MonitorStatusEnum => (s === 'online' || s === 'up') ? 'up' : (s === 'offline' || s === 'down') ? 'down' : 'unknown'

export function toMeshMonApi(multi: MultiNetworkAnalysis): MeshMonApi {
  const out: MeshMonApi = { networks: {} }
  for (const [netId, net] of Object.entries(multi.networks)) {
    // Nodes
    const nodes: Record<string, { node_id: string; status: 'online' | 'offline' | 'unknown'; version: string }> = {}
    for (const [nodeId, na] of Object.entries(net.node_analyses)) {
      nodes[nodeId] = {
        node_id: nodeId,
        status: (na.node_status as any) || 'unknown',
        version: na.node_info?.version || 'unknown',
      }
    }

    // Connections (directed)
    const connections: Array<{ src_node: { name: string; rtt: number; conn_type: 'up' | 'down' | 'unknown' }, dest_node: { name: string; rtt: number; conn_type: 'up' | 'down' | 'unknown' } }> = []
    for (const [src, na] of Object.entries(net.node_analyses)) {
      for (const [dst, detail] of Object.entries(na.outbound_info || {})) {
        connections.push({
          src_node: { name: src, rtt: (detail as any).rtt || 0, conn_type: statusToConnType((detail as any).status) },
          dest_node: { name: dst, rtt: (detail as any).rtt || 0, conn_type: 'unknown' },
        })
      }
    }

    // Monitors
    // Distribute monitors into deterministic groups so the UI can render group sections
    const GROUPS = ['alpha', 'beta', 'gamma', 'default'] as const
    const monitorEntries = Object.entries(net.monitor_analyses || {})
    const monitors = monitorEntries.map(([mid, ma], idx) => ({
      monitor_id: mid,
      name: mid,
      group: GROUPS[idx % GROUPS.length],
      status: monStatusToEnum((ma as any).monitor_status),
    }))

    // Monitor connections
    const monitor_connections: Array<{ node_id: string; monitor_id: string; status: MonitorStatusEnum; rtt: number }> = []
    for (const [mid, ma] of Object.entries(net.monitor_analyses || {})) {
      for (const [nid, det] of Object.entries((ma as MonitorAnalysis).inbound_info || {})) {
        monitor_connections.push({
          node_id: nid,
          monitor_id: mid,
          status: monStatusToEnum((det as any).status),
          rtt: (det as any).rtt || 0,
        })
      }
    }

    ;(out.networks as any)[netId] = { nodes, connections, monitors, monitor_connections }
  }
  return out
}

export const mockMeshMonApi: MeshMonApi = toMeshMonApi(mockMultiNetworkAnalysis)
