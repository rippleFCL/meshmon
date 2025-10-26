import { useMemo } from 'react'
import type { Edge, Node } from 'reactflow'
import type { MeshMonApi } from '../../../types'
// no layout utilities needed here; positions are computed by layout engines

// Produces graph data (nodes, edges, adjacency) without applying any layout.
// Positions are neutral; actual coordinates are computed by layout engines.
export function useProcessedGraph(
  networkData: MeshMonApi | null,
  selectedNetwork: string | null,
  isDark: boolean,
  hideOnlineByDefault: boolean,
  animationMode: 'never' | 'hover' | 'always',
  separateGroups: boolean = false
) {
  return useMemo(() => {
    if (!networkData?.networks || !selectedNetwork) {
      return { processedNodes: [] as Node[], processedEdges: [] as Edge[], nodeToEdgesMap: new Map<string, Set<string>>(), nodeToNeighborsMap: new Map<string, Set<string>>() }
    }
    const network = networkData.networks[selectedNetwork]
    if (!network) return { processedNodes: [], processedEdges: [], nodeToEdgesMap: new Map(), nodeToNeighborsMap: new Map() }

    const nodes: Node[] = []
    const edges: Edge[] = []
    const nodeIds = Object.keys(network.nodes)
    const monitorIds = network.monitors.map(m => m.monitor_id)

    type NodeMetric = { status: 'online' | 'offline' | 'unknown'; version: string; inTotal: number; inOnline: number; inSum: number; inCount: number; outTotal: number; outOnline: number; outSum: number; outCount: number }
    const nodeMetrics: Record<string, NodeMetric> = Object.fromEntries(nodeIds.map(id => [id, {
      status: network.nodes[id].status as any,
      version: network.nodes[id].version,
      inTotal: 0, inOnline: 0, inSum: 0, inCount: 0,
      outTotal: 0, outOnline: 0, outSum: 0, outCount: 0,
    }]))
    const addRTT = (sum: number, count: number, rtt: number) => (typeof rtt === 'number' && isFinite(rtt) && rtt > 0 ? { sum: sum + rtt, count: count + 1 } : { sum, count })
    for (const c of network.connections) {
      const a = c.src_node, b = c.dest_node
      if (nodeMetrics[a.name]) {
        nodeMetrics[a.name].outTotal++; if (a.conn_type === 'up') nodeMetrics[a.name].outOnline++
        const r = addRTT(nodeMetrics[a.name].outSum, nodeMetrics[a.name].outCount, a.rtt); nodeMetrics[a.name].outSum = r.sum; nodeMetrics[a.name].outCount = r.count
      }
      if (nodeMetrics[b.name]) {
        nodeMetrics[b.name].inTotal++; if (a.conn_type === 'up') nodeMetrics[b.name].inOnline++
        const r = addRTT(nodeMetrics[b.name].inSum, nodeMetrics[b.name].inCount, a.rtt); nodeMetrics[b.name].inSum = r.sum; nodeMetrics[b.name].inCount = r.count
      }
      if (nodeMetrics[b.name]) {
        nodeMetrics[b.name].outTotal++; if (b.conn_type === 'up') nodeMetrics[b.name].outOnline++
        const r2 = addRTT(nodeMetrics[b.name].outSum, nodeMetrics[b.name].outCount, b.rtt); nodeMetrics[b.name].outSum = r2.sum; nodeMetrics[b.name].outCount = r2.count
      }
      if (nodeMetrics[a.name]) {
        nodeMetrics[a.name].inTotal++; if (b.conn_type === 'up') nodeMetrics[a.name].inOnline++
        const r3 = addRTT(nodeMetrics[a.name].inSum, nodeMetrics[a.name].inCount, b.rtt); nodeMetrics[a.name].inSum = r3.sum; nodeMetrics[a.name].inCount = r3.count
      }
    }
    const mapMonStatus = (s: 'up' | 'down' | 'unknown') => s === 'up' ? 'online' : s === 'down' ? 'offline' : 'unknown'
    type MonMetric = { status: 'online' | 'offline' | 'unknown'; inTotal: number; inOnline: number }
    const monMetrics: Record<string, MonMetric> = Object.fromEntries(monitorIds.map(id => [id, { status: mapMonStatus(network.monitors.find(m => m.monitor_id === id)?.status || 'unknown'), inTotal: 0, inOnline: 0 }]))
    const monitorInboundMap: Record<string, Record<string, { online: boolean; rtt: number }>> = {}
    const monitorGroupMap: Record<string, string> = Object.fromEntries(
      network.monitors.map(m => [m.monitor_id, (m as any).group ?? 'default'])
    )
    const monitorNameMap: Record<string, string> = Object.fromEntries(
      network.monitors.map(m => [m.monitor_id, (m as any).name || m.monitor_id])
    )
    for (const mId of monitorIds) monitorInboundMap[mId] = {}
    for (const mc of network.monitor_connections) {
      if (!monitorInboundMap[mc.monitor_id]) monitorInboundMap[mc.monitor_id] = {}
      monitorInboundMap[mc.monitor_id][mc.node_id] = { online: mc.status === 'up', rtt: mc.rtt || 0 }
      if (monMetrics[mc.monitor_id]) { monMetrics[mc.monitor_id].inTotal++; if (mc.status === 'up') monMetrics[mc.monitor_id].inOnline++ }
    }

  const nodeMap = new Map<string, any>()

    const sortedNodes = nodeIds
      .map(nodeId => ({ id: nodeId, type: 'node', metrics: nodeMetrics[nodeId], totalConnections: (nodeMetrics[nodeId].inTotal || 0) + (nodeMetrics[nodeId].outTotal || 0) }))
      .sort((a, b) => b.totalConnections - a.totalConnections)
    const sortedMonitors = monitorIds.map(monitorId => ({ id: monitorId, type: 'monitor', metrics: monMetrics[monitorId], totalConnections: monMetrics[monitorId]?.inTotal || 0 }))

    // Build nodes without layout positions; engines will compute positions later.
    const pushNode = (entityId: string, m: any, totalConnections: number) => {
      const nodeData = {
        id: entityId,
        type: 'meshNode',
        position: { x: 0, y: 0 },
        data: {
          nodeId: entityId,
          label: entityId,
          status: m.status,
          avgRtt: m.inCount > 0 ? (m.inSum / m.inCount) : 0,
          inboundCount: m.inTotal,
          inboundOnlineCount: m.inOnline,
          outboundCount: m.outTotal,
          totalConnections,
          version: m.version || 'unknown',
          onHover: undefined,
          isHighlighted: false,
          isDimmed: false,
          isPanning: false,
        },
      }
      nodes.push(nodeData as any)
      nodeMap.set(entityId, nodeData)
    }
    const pushMonitor = (entityId: string, m: any, totalConnections: number) => {
      const monitorData = {
        id: entityId,
        type: 'monitorNode',
        position: { x: 0, y: 0 },
        data: {
          nodeId: entityId,
          label: monitorNameMap[entityId] ?? entityId,
          status: m.status,
          avgRtt: 0,
          inboundCount: m.inTotal,
          inboundOnlineCount: m.inOnline,
          totalConnections,
          onHover: undefined,
          isHighlighted: false,
          isDimmed: false,
          isPanning: false,
        },
      }
      nodes.push(monitorData as any)
      nodeMap.set(entityId, monitorData)
    }
    sortedNodes.forEach((entityInfo) => {
      const { id: entityId, metrics: m, totalConnections } = entityInfo as any
      pushNode(entityId, m, totalConnections)
    })
    sortedMonitors.forEach((entityInfo) => {
      const { id: entityId, metrics: m, totalConnections } = entityInfo as any
      pushMonitor(entityId, m, totalConnections)
    })

    // Edges
    const pairKey = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`)
    const pairMap = new Map<string, { aToB?: { online: boolean, rtt: number }, bToA?: { online: boolean, rtt: number } }>()
    for (const conn of network.connections) {
      const a = conn.src_node.name
      const b = conn.dest_node.name
      if (!nodeIds.includes(a) || !nodeIds.includes(b)) continue
      const small = a < b ? a : b
      const large = a < b ? b : a
      const smallToLarge = (small === a) ? conn.src_node : conn.dest_node
      const largeToSmall = (small === a) ? conn.dest_node : conn.src_node
      const key = pairKey(small, large)
      const rec = pairMap.get(key) || {}
      rec.aToB = { online: smallToLarge.conn_type === 'up', rtt: smallToLarge.rtt || 0 }
      rec.bToA = { online: largeToSmall.conn_type === 'up', rtt: largeToSmall.rtt || 0 }
      pairMap.set(key, rec)
    }

    for (const [key, rec] of pairMap.entries()) {
      const [a, b] = key.split('|')
      const aNode = nodeMap.get(a)
      const bNode = nodeMap.get(b)
      if (!aNode || !bNode) continue
      const hasAtoB = rec.aToB !== undefined
      const hasBtoA = rec.bToA !== undefined
      const aOnline = rec.aToB?.online ?? false
      const bOnline = rec.bToA?.online ?? false
      const bothOnline = hasAtoB && hasBtoA && aOnline && bOnline
      const bothDown = hasAtoB && hasBtoA && !aOnline && !bOnline
      const partial = hasAtoB && hasBtoA && ((aOnline && !bOnline) || (!aOnline && bOnline))
      const anyOnline = aOnline || bOnline
      const rttA = rec.aToB?.rtt
      const rttB = rec.bToA?.rtt
      const showDefaultLabels = false
      let labelText: string | undefined = undefined
      if (hasAtoB && hasBtoA) {
        if (showDefaultLabels && anyOnline) {
          const left = aOnline && typeof rttA === 'number' ? `${(rttA as number).toFixed(0)}ms` : 'offline'
          const right = bOnline && typeof rttB === 'number' ? `${(rttB as number).toFixed(0)}ms` : 'offline'
          labelText = `${left} →  |  ← ${right}`
        }
      } else if (hasAtoB) {
        if (showDefaultLabels && (aOnline || !hideOnlineByDefault)) {
          const left = aOnline && typeof rttA === 'number' ? `${(rttA as number).toFixed(0)}ms` : 'offline'
          labelText = `${left} →`
        }
      } else if (hasBtoA) {
        if (showDefaultLabels && (bOnline || !hideOnlineByDefault)) {
          const right = bOnline && typeof rttB === 'number' ? `${(rttB as number).toFixed(0)}ms` : 'offline'
          labelText = `← ${right}`
        }
      }
      let strokeColor = '#22c55e'
      let strokeDasharray = '0'
      if (hasAtoB && hasBtoA) {
        if (bothDown) { strokeColor = '#ef4444'; strokeDasharray = '6,3' }
        else if (partial) { strokeColor = '#eab308'; strokeDasharray = '6,3' }
        else if (bothOnline) { strokeColor = '#22c55e'; strokeDasharray = '0' }
      } else if (hasAtoB) {
        strokeColor = aOnline ? '#22c55e' : '#ef4444'
        strokeDasharray = aOnline ? '0' : '6,3'
      } else if (hasBtoA) {
        strokeColor = bOnline ? '#22c55e' : '#ef4444'
        strokeDasharray = bOnline ? '0' : '6,3'
      }
      const rttForStrength = (aOnline ? (rttA ?? 0) : Infinity) < (bOnline ? (rttB ?? 0) : Infinity)
        ? (aOnline ? (rttA ?? 0) : (bOnline ? (rttB ?? 0) : 0))
        : (bOnline ? (rttB ?? 0) : (aOnline ? (rttA ?? 0) : 0))
      const strength = anyOnline ? Math.max(1, 5 - ((rttForStrength as number) / 50)) : 0.5
      const baseStrokeWidth = Math.max(1.5, Math.min(4, strength))
      const strokeWidth = baseStrokeWidth
      const computedOpacity = anyOnline ? 0.7 : 0.6
      const baseOpacity = (hasAtoB && hasBtoA) ? (bothOnline && hideOnlineByDefault ? 0 : computedOpacity) : ((anyOnline && hideOnlineByDefault) ? 0 : computedOpacity)
      const fmtMs = (v?: number) => (typeof v === 'number' && isFinite(v)) ? `${Math.round(v)}ms` : 'offline'
      const fullLabelText: string | undefined = (() => {
        if (hasAtoB && hasBtoA) {
          const left = aOnline ? fmtMs(rttA) : 'offline'
          const right = bOnline ? fmtMs(rttB) : 'offline'
          return `${left} →  |  ← ${right}`
        } else if (hasAtoB) {
          return aOnline ? `${fmtMs(rttA)} →` : '→ offline'
        } else if (hasBtoA) {
          return bOnline ? `← ${fmtMs(rttB)}` : 'offline ←'
        }
        return undefined
      })()
      let orientedSource = a
      let orientedTarget = b
      if (partial) { if (aOnline && !bOnline) { orientedSource = a; orientedTarget = b } else if (bOnline && !aOnline) { orientedSource = b; orientedTarget = a } }
      else if (hasAtoB && !hasBtoA) { orientedSource = a; orientedTarget = b }
      else if (!hasAtoB && hasBtoA) { orientedSource = b; orientedTarget = a }
      const isUnidirectional = (hasAtoB && !hasBtoA) || (!hasAtoB && hasBtoA)
      const canAnimate = partial || isUnidirectional
      const isAnimatedNow = (animationMode === 'always') ? !!canAnimate : false
      edges.push({
        id: `${a}-${b}`,
        source: orientedSource,
        sourceHandle: 's',
        target: orientedTarget,
        targetHandle: 't',
        style: {
          stroke: strokeColor,
          strokeWidth,
          ...(isAnimatedNow ? { strokeDasharray: '8 4', animation: 'dashdraw 1s linear infinite' } : { strokeDasharray }),
          opacity: baseOpacity,
        },
        label: labelText,
        labelStyle: labelText ? {
          fontSize: 11,
          fontWeight: '600',
          fill: bothOnline ? '#16a34a' : (bothDown ? '#ef4444' : (partial ? '#eab308' : (strokeColor === '#22c55e' ? '#16a34a' : (strokeColor === '#eab308' ? '#eab308' : '#ef4444')))),
          background: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
          padding: '2px 6px',
          borderRadius: '12px',
          border: bothOnline ? '1px solid #22c55e' : (bothDown ? '1px solid #ef4444' : (partial ? '1px solid #eab308' : (strokeColor === '#22c55e' ? '1px solid #22c55e' : (strokeColor === '#eab308' ? '1px solid #eab308' : '1px solid #ef4444')))),
        } : undefined,
        labelBgStyle: labelText ? { fill: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)', fillOpacity: 0.9 } : undefined,
        data: {
          isOnline: anyOnline,
          isMonitorEdge: false,
          canAnimate,
          originalLabel: fullLabelText,
          originalLabelStyle: fullLabelText ? {
            fontSize: 11,
            fontWeight: '600',
            fill: bothOnline ? '#16a34a' : (bothDown ? '#ef4444' : (partial ? '#eab308' : (strokeColor === '#22c55e' ? '#16a34a' : (strokeColor === '#eab308' ? '#eab308' : '#ef4444')))),
            background: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
            padding: '2px 6px',
            borderRadius: '12px',
            border: bothOnline ? '1px solid #22c55e' : (bothDown ? '1px solid #ef4444' : (partial ? '1px solid #eab308' : (strokeColor === '#22c55e' ? '1px solid #22c55e' : (strokeColor === '#eab308' ? '1px solid #eab308' : '1px solid #ef4444')))),
          } : undefined,
          originalLabelBgStyle: fullLabelText ? { fill: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)', fillOpacity: 0.9 } : undefined,
          originalOpacity: computedOpacity,
          baseOpacity,
          aToBOnline: aOnline,
          bToAOnline: bOnline,
          hasAtoB,
          hasBtoA,
        },
        animated: isAnimatedNow,
        type: 'floating',
        markerStart: (() => {
          const backOnline = (orientedSource === a) ? bOnline : aOnline
          const exist = (orientedSource === a) ? hasBtoA : hasAtoB
          return exist ? { type: 3 as any, color: backOnline ? '#22c55e' : '#ef4444', width: 12, height: 12 } : undefined
        })(),
        markerEnd: (() => {
          const fwdOnline = (orientedSource === a) ? aOnline : bOnline
          const exist = (orientedSource === a) ? hasAtoB : hasBtoA
          return exist ? { type: 3 as any, color: fwdOnline ? '#22c55e' : '#ef4444', width: 12, height: 12 } : undefined
        })(),
      } as any)
    }

    // Node -> monitor edges (unified mode)
    if (!separateGroups) {
      for (const sourceNodeId of nodeIds) {
        for (const monitorId of monitorIds) {
          const inbound = monitorInboundMap[monitorId]?.[sourceNodeId]
          if (!inbound) continue
          const isOnline = inbound.online
          const rtt = inbound.rtt || 0
          const strength = isOnline ? Math.max(1, 5 - (rtt / 50)) : 0.5
          const baseStrokeWidth = Math.max(1.5, Math.min(4, strength))
          const strokeWidth = baseStrokeWidth
          const computedOpacity = isOnline ? 0.7 : 0.6
          const baseOpacity = isOnline && hideOnlineByDefault ? 0 : computedOpacity
          const edgeId = `${sourceNodeId}-${monitorId}`
          const canAnimateMon = true
          const isAnimatedNowMon = (animationMode === 'always') ? true : false
          edges.push({
            id: edgeId,
            source: sourceNodeId,
            sourceHandle: 's',
            target: monitorId,
            targetHandle: 't',
            style: {
              stroke: isOnline ? '#a855f7' : '#ef4444',
              strokeWidth,
              ...(isAnimatedNowMon ? { strokeDasharray: '8 4', animation: 'dashdraw 1s linear infinite' } : { strokeDasharray: isOnline ? '0' : '6,3' }),
              opacity: baseOpacity,
            },
            label: isOnline && false ? `${rtt.toFixed(0)}ms` : undefined,
            data: {
              isOnline: isOnline,
              isMonitorEdge: true,
              canAnimate: canAnimateMon,
              originalLabel: isOnline ? `${rtt.toFixed(0)}ms` : undefined,
              originalOpacity: computedOpacity,
              baseOpacity,
            },
            animated: isAnimatedNowMon,
            type: 'floating',
            markerEnd: { type: 3 as any, color: isOnline ? '#a855f7' : '#ef4444', width: 12, height: 12 },
          } as any)
        }
      }
    }

    // Adjacency maps for hover/focus
    const edgeMap = new Map<string, Set<string>>()
    const neighborMap = new Map<string, Set<string>>()
    edges.forEach((edge) => {
      if (!edgeMap.has(edge.source)) edgeMap.set(edge.source, new Set())
      if (!edgeMap.has(edge.target)) edgeMap.set(edge.target, new Set())
      edgeMap.get(edge.source)!.add(edge.id)
      edgeMap.get(edge.target)!.add(edge.id)
      if (!neighborMap.has(edge.source)) neighborMap.set(edge.source, new Set())
      if (!neighborMap.has(edge.target)) neighborMap.set(edge.target, new Set())
      neighborMap.get(edge.source)!.add(edge.target)
      neighborMap.get(edge.target)!.add(edge.source)
    })

    // If separateGroups is requested, rebuild nodes and edges into per-group clusters
    if (separateGroups) {
      const groups = Array.from(new Set(Object.values(monitorGroupMap)))
      const groupedNodes: Node[] = []
      const groupedEdges: Edge[] = []

      // Precompute node set per group from monitor inbound connections
      const nodesPerGroup: Record<string, Set<string>> = {}
      for (const g of groups) nodesPerGroup[g] = new Set<string>()
      for (const [mid, inbound] of Object.entries(monitorInboundMap)) {
        const g = monitorGroupMap[mid] || 'default'
        for (const nid of Object.keys(inbound)) nodesPerGroup[g].add(nid)
      }

      // Helper to clone node data with a grouped id
      const cloneNode = (orig: any, group: string): Node => {
        const cloneId = `${orig.id}::g=${group}`
        return ({
          id: cloneId,
          type: orig.type,
          position: { x: 0, y: 0 },
          data: { ...orig.data, group, nodeId: cloneId },
        } as any)
      }

      // Build per-group subgraphs
      for (const g of groups) {
        const nodeSet = nodesPerGroup[g]
        if (!nodeSet || nodeSet.size === 0) continue
        // Add node copies
        for (const nid of nodeSet) {
          const baseNode = nodeMap.get(nid)
          if (baseNode) groupedNodes.push(cloneNode(baseNode, g))
        }
        // Add monitor copies for group
        const groupMonitorIds = monitorIds.filter(mid => monitorGroupMap[mid] === g)
        for (const mid of groupMonitorIds) {
          const baseMon = nodeMap.get(mid)
          if (baseMon) groupedNodes.push(cloneNode(baseMon, g))
        }

        // Add node-to-node edges within group (use underlying mesh connections, but scoped to grouped ids)
        for (const [key, rec] of pairMap.entries()) {
          const [a, b] = key.split('|')
          if (!nodeSet.has(a) || !nodeSet.has(b)) continue
          const aOnline = rec.aToB?.online ?? false
          const bOnline = rec.bToA?.online ?? false
          const hasAtoB = rec.aToB !== undefined
          const hasBtoA = rec.bToA !== undefined
          const bothOnline = hasAtoB && hasBtoA && aOnline && bOnline
          const bothDown = hasAtoB && hasBtoA && !aOnline && !bOnline
          const partial = hasAtoB && hasBtoA && ((aOnline && !bOnline) || (!aOnline && bOnline))
          const anyOnline = aOnline || bOnline
          const rttA = rec.aToB?.rtt
          const rttB = rec.bToA?.rtt
          let strokeColor = '#22c55e'
          let strokeDasharray = '0'
          if (hasAtoB && hasBtoA) {
            if (bothDown) { strokeColor = '#ef4444'; strokeDasharray = '6,3' }
            else if (partial) { strokeColor = '#eab308'; strokeDasharray = '6,3' }
            else if (bothOnline) { strokeColor = '#22c55e'; strokeDasharray = '0' }
          } else if (hasAtoB) {
            strokeColor = aOnline ? '#22c55e' : '#ef4444'
            strokeDasharray = aOnline ? '0' : '6,3'
          } else if (!hasAtoB && hasBtoA) {
            strokeColor = bOnline ? '#22c55e' : '#ef4444'
            strokeDasharray = bOnline ? '0' : '6,3'
          }
          const rttForStrength = (aOnline ? (rttA ?? 0) : Infinity) < (bOnline ? (rttB ?? 0) : Infinity)
            ? (aOnline ? (rttA ?? 0) : (bOnline ? (rttB ?? 0) : 0))
            : (bOnline ? (rttB ?? 0) : (aOnline ? (rttA ?? 0) : 0))
          const strength = anyOnline ? Math.max(1, 5 - ((rttForStrength as number) / 50)) : 0.5
          const baseStrokeWidth = Math.max(1.5, Math.min(4, strength))
          const strokeWidth = baseStrokeWidth
          const computedOpacity = anyOnline ? 0.7 : 0.6
          const baseOpacity = (hasAtoB && hasBtoA) ? (bothOnline && hideOnlineByDefault ? 0 : computedOpacity) : ((anyOnline && hideOnlineByDefault) ? 0 : computedOpacity)
          let orientedSource = a
          let orientedTarget = b
          if (partial) { if (aOnline && !bOnline) { orientedSource = a; orientedTarget = b } else if (bOnline && !aOnline) { orientedSource = b; orientedTarget = a } }
          else if (hasAtoB && !hasBtoA) { orientedSource = a; orientedTarget = b }
          else if (!hasAtoB && hasBtoA) { orientedSource = b; orientedTarget = a }
          const isUnidirectional = (hasAtoB && !hasBtoA) || (!hasAtoB && hasBtoA)
          const canAnimate = partial || isUnidirectional
          const isAnimatedNow = (animationMode === 'always') ? !!canAnimate : false
          groupedEdges.push({
            id: `${a}::g=${g}-${b}::g=${g}`,
            source: `${orientedSource}::g=${g}`,
            sourceHandle: 's',
            target: `${orientedTarget}::g=${g}`,
            targetHandle: 't',
            style: {
              stroke: strokeColor,
              strokeWidth,
              ...(isAnimatedNow ? { strokeDasharray: '8 4', animation: 'dashdraw 1s linear infinite' } : { strokeDasharray }),
              opacity: baseOpacity,
            },
            data: {
              isOnline: anyOnline,
              isMonitorEdge: false,
              canAnimate,
              originalOpacity: computedOpacity,
              baseOpacity,
              originalLabel: undefined,
              originalLabelStyle: undefined,
              originalLabelBgStyle: undefined,
              aToBOnline: aOnline,
              bToAOnline: bOnline,
              hasAtoB,
              hasBtoA,
            },
            animated: isAnimatedNow,
            type: 'floating',
            markerStart: (() => {
              const backOnline = (orientedSource === a) ? bOnline : aOnline
              const exist = (orientedSource === a) ? hasBtoA : hasAtoB
              return exist ? { type: 3 as any, color: backOnline ? '#22c55e' : '#ef4444', width: 12, height: 12 } : undefined
            })(),
            markerEnd: (() => {
              const fwdOnline = (orientedSource === a) ? aOnline : bOnline
              const exist = (orientedSource === a) ? hasAtoB : hasBtoA
              return exist ? { type: 3 as any, color: fwdOnline ? '#22c55e' : '#ef4444', width: 12, height: 12 } : undefined
            })(),
          } as any)
        }
        // Note: in separated mode we intentionally omit node-to-node edges to keep clusters simple
        // Add node->monitor edges within group
        for (const mid of groupMonitorIds) {
          const inbound = monitorInboundMap[mid] || {}
          for (const nid of Object.keys(inbound)) {
            if (!nodeSet.has(nid)) continue
            const isOnline = inbound[nid]?.online ?? false
            const rtt = inbound[nid]?.rtt || 0
            const strength = isOnline ? Math.max(1, 5 - (rtt / 50)) : 0.5
            const baseStrokeWidth = Math.max(1.5, Math.min(4, strength))
            const strokeWidth = baseStrokeWidth
            const computedOpacity = isOnline ? 0.7 : 0.6
            const baseOpacity = isOnline && hideOnlineByDefault ? 0 : computedOpacity
            const canAnimateMon = true
            const isAnimatedNowMon = (animationMode === 'always') ? true : false
            groupedEdges.push({
              id: `${nid}::g=${g}-${mid}::g=${g}`,
              source: `${nid}::g=${g}`,
              sourceHandle: 's',
              target: `${mid}::g=${g}`,
              targetHandle: 't',
              style: {
                stroke: isOnline ? '#a855f7' : '#ef4444',
                strokeWidth,
                ...(isAnimatedNowMon ? { strokeDasharray: '8 4', animation: 'dashdraw 1s linear infinite' } : { strokeDasharray: isOnline ? '0' : '6,3' }),
                opacity: baseOpacity,
              },
              data: {
                isOnline,
                isMonitorEdge: true,
                canAnimate: canAnimateMon,
                originalLabel: isOnline ? `${rtt.toFixed(0)}ms` : undefined,
                originalLabelStyle: undefined,
                originalLabelBgStyle: undefined,
                originalOpacity: computedOpacity,
                baseOpacity,
              },
              animated: isAnimatedNowMon,
              type: 'floating',
              markerEnd: { type: 3 as any, color: isOnline ? '#a855f7' : '#ef4444', width: 12, height: 12 },
            } as any)
          }
        }
      }

      // Add an additional cluster for all nodes (nodes-only view, entire network)
      {
        const g = 'all'
        // Add all node clones
        for (const nid of nodeIds) {
          const baseNode = nodeMap.get(nid)
          if (baseNode) groupedNodes.push(cloneNode(baseNode, g))
        }
        // Add node-to-node edges for all node pairs
        for (const [key, rec] of pairMap.entries()) {
          const [a, b] = key.split('|')
          const aOnline = rec.aToB?.online ?? false
          const bOnline = rec.bToA?.online ?? false
          const hasAtoB = rec.aToB !== undefined
          const hasBtoA = rec.bToA !== undefined
          const bothOnline = hasAtoB && hasBtoA && aOnline && bOnline
          const bothDown = hasAtoB && hasBtoA && !aOnline && !bOnline
          const partial = hasAtoB && hasBtoA && ((aOnline && !bOnline) || (!aOnline && bOnline))
          const anyOnline = aOnline || bOnline
          const rttA = rec.aToB?.rtt
          const rttB = rec.bToA?.rtt
          let strokeColor = '#22c55e'
          let strokeDasharray = '0'
          if (hasAtoB && hasBtoA) {
            if (bothDown) { strokeColor = '#ef4444'; strokeDasharray = '6,3' }
            else if (partial) { strokeColor = '#eab308'; strokeDasharray = '6,3' }
            else if (bothOnline) { strokeColor = '#22c55e'; strokeDasharray = '0' }
          } else if (hasAtoB) {
            strokeColor = aOnline ? '#22c55e' : '#ef4444'
            strokeDasharray = aOnline ? '0' : '6,3'
          } else if (!hasAtoB && hasBtoA) {
            strokeColor = bOnline ? '#22c55e' : '#ef4444'
            strokeDasharray = bOnline ? '0' : '6,3'
          }
          const rttForStrength = (aOnline ? (rttA ?? 0) : Infinity) < (bOnline ? (rttB ?? 0) : Infinity)
            ? (aOnline ? (rttA ?? 0) : (bOnline ? (rttB ?? 0) : 0))
            : (bOnline ? (rttB ?? 0) : (aOnline ? (rttA ?? 0) : 0))
          const strength = anyOnline ? Math.max(1, 5 - ((rttForStrength as number) / 50)) : 0.5
          const baseStrokeWidth = Math.max(1.5, Math.min(4, strength))
          const strokeWidth = baseStrokeWidth
          const computedOpacity = anyOnline ? 0.7 : 0.6
          const baseOpacity = (hasAtoB && hasBtoA) ? (bothOnline && hideOnlineByDefault ? 0 : computedOpacity) : ((anyOnline && hideOnlineByDefault) ? 0 : computedOpacity)
          let orientedSource = a
          let orientedTarget = b
          if (partial) { if (aOnline && !bOnline) { orientedSource = a; orientedTarget = b } else if (bOnline && !aOnline) { orientedSource = b; orientedTarget = a } }
          else if (hasAtoB && !hasBtoA) { orientedSource = a; orientedTarget = b }
          else if (!hasAtoB && hasBtoA) { orientedSource = b; orientedTarget = a }
          const isUnidirectional = (hasAtoB && !hasBtoA) || (!hasAtoB && hasBtoA)
          const canAnimate = partial || isUnidirectional
          const isAnimatedNow = (animationMode === 'always') ? !!canAnimate : false
          groupedEdges.push({
            id: `${a}::g=${g}-${b}::g=${g}`,
            source: `${orientedSource}::g=${g}`,
            sourceHandle: 's',
            target: `${orientedTarget}::g=${g}`,
            targetHandle: 't',
            style: {
              stroke: strokeColor,
              strokeWidth,
              ...(isAnimatedNow ? { strokeDasharray: '8 4', animation: 'dashdraw 1s linear infinite' } : { strokeDasharray }),
              opacity: baseOpacity,
            },
            data: {
              isOnline: anyOnline,
              isMonitorEdge: false,
              canAnimate,
              originalOpacity: computedOpacity,
              baseOpacity,
              originalLabel: undefined,
              originalLabelStyle: undefined,
              originalLabelBgStyle: undefined,
              aToBOnline: aOnline,
              bToAOnline: bOnline,
              hasAtoB,
              hasBtoA,
            },
            animated: isAnimatedNow,
            type: 'floating',
            markerStart: (() => {
              const backOnline = (orientedSource === a) ? bOnline : aOnline
              const exist = (orientedSource === a) ? hasBtoA : hasAtoB
              return exist ? { type: 3 as any, color: backOnline ? '#22c55e' : '#ef4444', width: 12, height: 12 } : undefined
            })(),
            markerEnd: (() => {
              const fwdOnline = (orientedSource === a) ? aOnline : bOnline
              const exist = (orientedSource === a) ? hasAtoB : hasBtoA
              return exist ? { type: 3 as any, color: fwdOnline ? '#22c55e' : '#ef4444', width: 12, height: 12 } : undefined
            })(),
          } as any)
        }
      }

      // Replace unified graph with grouped graph
      const edgeMap2 = new Map<string, Set<string>>()
      const neighborMap2 = new Map<string, Set<string>>()
      groupedEdges.forEach((edge) => {
        if (!edgeMap2.has(edge.source)) edgeMap2.set(edge.source, new Set())
        if (!edgeMap2.has(edge.target)) edgeMap2.set(edge.target, new Set())
        edgeMap2.get(edge.source)!.add(edge.id)
        edgeMap2.get(edge.target)!.add(edge.id)
        if (!neighborMap2.has(edge.source)) neighborMap2.set(edge.source, new Set())
        if (!neighborMap2.has(edge.target)) neighborMap2.set(edge.target, new Set())
        neighborMap2.get(edge.source)!.add(edge.target)
        neighborMap2.get(edge.target)!.add(edge.source)
      })
      return { processedNodes: groupedNodes, processedEdges: groupedEdges, nodeToEdgesMap: edgeMap2, nodeToNeighborsMap: neighborMap2 }
    }

    return { processedNodes: nodes, processedEdges: edges, nodeToEdgesMap: edgeMap, nodeToNeighborsMap: neighborMap }
  }, [networkData, selectedNetwork, isDark, hideOnlineByDefault, animationMode, separateGroups])
}
