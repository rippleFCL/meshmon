import { useState, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { viewStore } from '@/api/viewStore'
import { useRefresh } from '../contexts/RefreshContext'
import { NetworkInfoNew } from '../types'
import { useTheme } from '../contexts/ThemeContext'
import NodeDetailCard from '../components/network/NodeDetailCard'
import MonitorDetailCard from '../components/network/MonitorDetailCard'

type NodeLink = { status: 'online' | 'offline' | 'unknown'; rtt: number }
type NodeAdj = Record<string, NodeLink>
type Agg = { average_rtt: number; online_connections: number; total_connections: number; status: 'online' | 'offline' | 'degraded' | 'unknown' }

// In-file prop interfaces removed; using extracted components

// In-file components and helpers removed; using extracted components instead

export default function NetworkDetail() {
    const { networkId } = useParams<{ networkId: string }>()
    const navigate = useNavigate()
    const { isDark } = useTheme()
    const { registerRefreshCallback } = useRefresh()
    const [network, setNetwork] = useState<NetworkInfoNew | null>(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
    const [expandedMonitors, setExpandedMonitors] = useState<Set<string>>(new Set())
    const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
    const [useUnifiedLayout, setUseUnifiedLayout] = useState(true)
    const groupsInitializedRef = useRef(false)

    const fetchData = useCallback(async (isInitialLoad = false) => {
        try {
            if (isInitialLoad) setLoading(true)
            else setRefreshing(true)
            await viewStore.refresh()
        } finally {
            if (isInitialLoad) setLoading(false)
            else setRefreshing(false)
        }
    }, [])

    useEffect(() => {
        const unsub = viewStore.subscribe((s) => {
            if (networkId && s.data?.networks[networkId]) {
                setNetwork(s.data.networks[networkId])
                setError(null)
            } else if (!s.loading) {
                setError(`Network "${networkId}" not found`)
            }
            setLoading(s.loading && !s.data)
            setRefreshing(s.loading && !!s.data)
        }, 10000)
        void fetchData(true)
        const cleanup = registerRefreshCallback(() => { void viewStore.refresh() })
        return () => { unsub(); cleanup() }
    }, [fetchData, registerRefreshCallback, networkId])

    // Initialize group expansion once per network and reconcile on refresh without opening new groups
    useEffect(() => {
        if (!network) return
        const currentGroups = new Set(network.monitors.map(m => m.group ?? 'default'))
        setExpandedGroups((prev) => {
            if (!groupsInitializedRef.current) {
                groupsInitializedRef.current = true
                // First time for this network: start with all non-default groups expanded
                return new Set(Array.from(currentGroups).filter(g => g !== 'default'))
            }
            // Reconcile: keep only groups that still exist; don't auto-open new ones
            const next = new Set<string>()
            prev.forEach(g => { if (g !== 'default' && currentGroups.has(g)) next.add(g) })
            return next
        })
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [network])

    // Reset initialization when switching to a different network
    useEffect(() => {
        groupsInitializedRef.current = false
        // Do not clear expandedGroups here; let the init effect set it appropriately next render
    }, [networkId])

    const toggleNode = (nodeId: string) => {
        const newExpanded = new Set(expandedNodes)
        if (newExpanded.has(nodeId)) {
            newExpanded.delete(nodeId)
        } else {
            newExpanded.add(nodeId)
        }
        setExpandedNodes(newExpanded)
    }

    const toggleMonitor = (monitorId: string) => {
        const newExpanded = new Set(expandedMonitors)
        if (newExpanded.has(monitorId)) {
            newExpanded.delete(monitorId)
        } else {
            newExpanded.add(monitorId)
        }
        setExpandedMonitors(newExpanded)
    }

    const expandAll = () => {
        if (network) {
            setExpandedNodes(new Set(Object.keys(network.nodes)))
            setExpandedMonitors(new Set(network.monitors.map(m => m.monitor_id)))
            const allGroups = Array.from(new Set(network.monitors.map(m => m.group ?? 'default')))
            setExpandedGroups(new Set(allGroups.filter(g => g !== 'default')))
        }
    }

    const collapseAll = () => {
        setExpandedNodes(new Set())
        setExpandedMonitors(new Set())
        setExpandedGroups(new Set())
    }

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="flex items-center space-x-4">
                    <button
                        onClick={() => navigate('/')}
                        className={`p-2 rounded-lg ${isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-100'}`}
                    >
                        <ArrowLeft className={`h-5 w-5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`} />
                    </button>
                    <div>
                        <h1 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>Network Details</h1>
                        <p className={`${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Loading network data...</p>
                    </div>
                </div>
            </div>
        )
    }

    if (error || !network) {
        return (
            <div className="space-y-6">
                <div className="flex items-center space-x-4">
                    <button
                        onClick={() => navigate('/')}
                        className={`p-2 rounded-lg transition-colors duration-200 ${isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                            }`}
                    >
                        <ArrowLeft className={`h-5 w-5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`} />
                    </button>
                    <div>
                        <h1 className={`text-2xl font-bold ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>Network Details</h1>
                        <p className={`${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Network information</p>
                    </div>
                </div>
                <div className="card p-6">
                    <div className={`text-center ${isDark ? 'text-red-400' : 'text-red-600'}`}>
                        <p>{error || 'Network not found'}</p>
                        <button
                            onClick={() => fetchData(true)}
                            className="btn btn-primary mt-4"
                        >
                            Retry
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    const nodeEntries = Object.values(network.nodes)
    const totalNodes = nodeEntries.length
    const onlineNodes = nodeEntries.filter(n => n.status === 'online').length
    const offlineNodes = nodeEntries.filter(n => n.status === 'offline').length
    const networkStatus = offlineNodes === 0 && onlineNodes === totalNodes && totalNodes > 0 ? 'Healthy' :
        onlineNodes > 0 ? 'Degraded' : 'Offline'

    const statusColor = offlineNodes === 0 && onlineNodes === totalNodes && totalNodes > 0 ? 'text-green-600 bg-green-100' :
        onlineNodes > 0 ? 'text-yellow-600 bg-yellow-100' :
            'text-red-600 bg-red-100'

    // Build node adjacency maps and aggregates
    const mapApiStatus = (t: 'up' | 'down' | 'unknown'): 'online' | 'offline' | 'unknown' =>
        t === 'up' ? 'online' : t === 'down' ? 'offline' : 'unknown'

    const nodeIds = Object.keys(network.nodes)
    const inboundMap: Record<string, NodeAdj> = {}
    const outboundMap: Record<string, NodeAdj> = {}
    nodeIds.forEach(id => { inboundMap[id] = {}; outboundMap[id] = {} })

    for (const c of network.connections) {
        const s = c.src_node
        const d = c.dest_node
        // src -> dest
        if (!outboundMap[s.name]) outboundMap[s.name] = {}
        if (!inboundMap[d.name]) inboundMap[d.name] = {}
        outboundMap[s.name][d.name] = { status: mapApiStatus(s.conn_type), rtt: s.rtt }
        inboundMap[d.name][s.name] = { status: mapApiStatus(s.conn_type), rtt: s.rtt }
        // dest -> src
        if (!outboundMap[d.name]) outboundMap[d.name] = {}
        if (!inboundMap[s.name]) inboundMap[s.name] = {}
        outboundMap[d.name][s.name] = { status: mapApiStatus(d.conn_type), rtt: d.rtt }
        inboundMap[s.name][d.name] = { status: mapApiStatus(d.conn_type), rtt: d.rtt }
    }

    const computeAgg = (adj: NodeAdj): Agg => {
        const vals = Object.values(adj)
        const total = vals.length
        const online = vals.filter(v => v.status === 'online').length
        const avg = total > 0 ? vals.reduce((sum, v) => sum + (v.rtt > 0 ? v.rtt : 0), 0) / total : 0
        const status = total === 0 ? 'unknown' : online === total ? 'online' : online === 0 ? 'offline' : 'degraded'
        return { average_rtt: avg, online_connections: online, total_connections: total, status }
    }

    const inboundAggs: Record<string, Agg> = {}
    const outboundAggs: Record<string, Agg> = {}
    nodeIds.forEach(id => { inboundAggs[id] = computeAgg(inboundMap[id]); outboundAggs[id] = computeAgg(outboundMap[id]) })

    // Monitors inbound maps and aggregates
    const monitorIds = network.monitors.map(m => m.monitor_id)
    const monitorInbound: Record<string, Record<string, { status: 'online' | 'offline' | 'unknown'; rtt: number }>> = {}
    const monitorAggs: Record<string, Agg> = {}
    const monitorStatusMap: Record<string, 'online' | 'offline' | 'unknown'> = {}
    for (const m of network.monitors) {
        monitorInbound[m.monitor_id] = {}
        monitorStatusMap[m.monitor_id] = mapApiStatus(m.status)
    }
    for (const mc of network.monitor_connections) {
        const monId = mc.monitor_id
        if (!monitorInbound[monId]) monitorInbound[monId] = {}
        monitorInbound[monId][mc.node_id] = { status: mapApiStatus(mc.status), rtt: mc.rtt || 0 }
    }
    for (const monId of monitorIds) {
        monitorAggs[monId] = computeAgg(monitorInbound[monId] as NodeAdj)
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                    <button
                        onClick={() => navigate('/')}
                        className={`p-2 rounded-lg transition-colors duration-200 ${isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                            }`}
                    >
                        <ArrowLeft className={`h-5 w-5 ${isDark ? 'text-gray-300' : 'text-gray-700'}`} />
                    </button>
                    <div>
                        <h1 className={`text-2xl font-bold ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{networkId}</h1>
                        <p className={`${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Detailed network monitoring and node connections</p>
                    </div>
                </div>
                <div className="flex items-center space-x-3">
                    {refreshing && (
                        <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
                            <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
                            <span>Updating...</span>
                        </div>
                    )}

                    {/* Layout Toggle */}
                    <div className="flex items-center space-x-2">
                        <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                            Tables
                        </span>
                        <button
                            onClick={() => setUseUnifiedLayout(!useUnifiedLayout)}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${useUnifiedLayout
                                ? 'bg-blue-600'
                                : isDark
                                    ? 'bg-gray-600'
                                    : 'bg-gray-200'
                                }`}
                        >
                            <span
                                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${useUnifiedLayout ? 'translate-x-6' : 'translate-x-1'
                                    }`}
                            />
                        </button>
                        <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                            Unified
                        </span>
                    </div>

                    <button
                        onClick={expandAll}
                        className={`px-3 py-2 text-sm rounded transition-colors duration-200 ${isDark
                            ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                            : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                            }`}
                    >
                        Expand All
                    </button>
                    <button
                        onClick={collapseAll}
                        className={`px-3 py-2 text-sm rounded transition-colors duration-200 ${isDark
                            ? 'bg-gray-700 hover:bg-gray-600 text-gray-200'
                            : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                            }`}
                    >
                        Collapse All
                    </button>
                </div>
            </div>

            {/* Network Overview */}
            <div className="card p-6 data-fade">
                <div className="flex items-center justify-between mb-6">
                    <h3 className={`text-lg font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>Network Overview</h3>
                    <span className={`px-3 py-1 text-sm font-medium rounded-full ${statusColor}`}>
                        {networkStatus}
                    </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                    <div className={`text-center p-6 rounded-lg flex flex-col justify-center stats-update ${isDark ? 'bg-gray-700' : 'bg-gray-50'}`}>
                        <div className={`text-3xl font-bold mb-2 ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{totalNodes}</div>
                        <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Total Nodes</div>
                    </div>
                    <div className={`text-center p-6 rounded-lg flex flex-col justify-center stats-update ${isDark ? 'bg-green-900/20' : 'bg-green-50'}`}>
                        <div className={`text-3xl font-bold mb-2 ${isDark ? 'text-green-400' : 'text-green-600'}`}>{onlineNodes}</div>
                        <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Online Nodes</div>
                    </div>
                    <div className={`text-center p-6 rounded-lg flex flex-col justify-center stats-update ${isDark ? 'bg-red-900/20' : 'bg-red-50'}`}>
                        <div className={`text-3xl font-bold mb-2 ${isDark ? 'text-red-400' : 'text-red-600'}`}>{offlineNodes}</div>
                        <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Offline Nodes</div>
                    </div>
                    <div className={`text-center p-6 rounded-lg flex flex-col justify-center stats-update ${isDark ? 'bg-blue-900/20' : 'bg-blue-50'}`}>
                        <div className={`text-xl font-bold mb-2 ${isDark ? 'text-blue-400' : 'text-blue-600'} leading-tight`}>
                            {(() => {
                                const uniqueVersions = new Set(nodeEntries.map(n => n.version))
                                return uniqueVersions.size
                            })()}
                        </div>
                        <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Unique Versions</div>
                    </div>
                </div>
            </div>

            {/* Node Details */}
            <div className="data-fade">
                <h3 className={`text-lg font-medium mb-3 ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>Node Details</h3>
                <div className="space-y-2">
                    {Object.keys(network.nodes).map((nodeId) => (
                        <NodeDetailCard
                            key={nodeId}
                            nodeId={nodeId}
                            nodeStatus={network.nodes[nodeId].status}
                            inboundInfo={inboundMap[nodeId] || {}}
                            outboundInfo={outboundMap[nodeId] || {}}
                            inboundAgg={inboundAggs[nodeId]}
                            outboundAgg={outboundAggs[nodeId]}
                            version={network.nodes[nodeId].version}
                            isExpanded={expandedNodes.has(nodeId)}
                            onToggle={() => toggleNode(nodeId)}
                            useUnifiedLayout={useUnifiedLayout}
                        />
                    ))}
                </div>
            </div>

            {/* Monitor Details */}
            {network.monitors && network.monitors.length > 0 && (() => {
                // Group monitors by group
                const groups: Record<string, typeof network.monitors> = {}
                for (const m of network.monitors) {
                    const g = m.group ?? 'default'
                    if (!groups[g]) groups[g] = []
                    groups[g].push(m)
                }
                const defaultGroup = groups['default'] || []
                const groupNames = Object.keys(groups).filter(g => g !== 'default').sort()
                return (
                    <div className="data-fade">
                        <h3 className={`text-lg font-medium mb-3 ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>Monitor Details</h3>
                        <div className="space-y-3">
                            {defaultGroup.length > 0 && (
                                <div className="space-y-2">
                                    {defaultGroup.map((m) => (
                                        <MonitorDetailCard
                                            key={m.monitor_id}
                                            monitorName={m.name || m.monitor_id}
                                            monitorStatus={monitorStatusMap[m.monitor_id]}
                                            inboundInfo={monitorInbound[m.monitor_id] || {}}
                                            inboundAgg={monitorAggs[m.monitor_id]}
                                            isExpanded={expandedMonitors.has(m.monitor_id)}
                                            onToggle={() => toggleMonitor(m.monitor_id)}
                                            useUnifiedLayout={useUnifiedLayout}
                                        />
                                    ))}
                                </div>
                            )}
                            {groupNames.map((g) => {
                                const isOpen = expandedGroups.has(g)
                                const toggleGroup = () => {
                                    const next = new Set(expandedGroups)
                                    if (next.has(g)) next.delete(g)
                                    else next.add(g)
                                    setExpandedGroups(next)
                                }
                                const groupMons = groups[g]
                                const total = groupMons.length
                                const online = groupMons.filter(m => monitorStatusMap[m.monitor_id] === 'online').length
                                const offline = groupMons.filter(m => monitorStatusMap[m.monitor_id] === 'offline').length
                                const allOnline = online === total && total > 0
                                const allOffline = offline === total && total > 0
                                const anyDown = offline > 0 && !allOffline
                                const statusLightClass = (() => {
                                    if (allOnline) return isDark ? 'bg-green-900/30 text-green-400' : 'bg-green-100 text-green-700'
                                    if (allOffline) return isDark ? 'bg-red-900/30 text-red-400' : 'bg-red-100 text-red-700'
                                    if (anyDown) return isDark ? 'bg-yellow-900/30 text-yellow-400' : 'bg-yellow-100 text-yellow-700'
                                    return isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-700'
                                })()
                                return (
                                    <div key={g} className="card p-0 overflow-hidden">
                                        <button
                                            onClick={toggleGroup}
                                            className={`w-full flex items-center justify-between py-2 px-3 ${isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50'}`}
                                            aria-expanded={isOpen}
                                        >
                                            <div className="flex items-center gap-2">
                                                <span className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{isOpen ? '▼' : '▶'}</span>
                                                <span className={`font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{g}</span>
                                                <span className={`px-2 py-0.5 text-xs font-medium rounded ${isDark ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-700'}`}>
                                                    Group
                                                </span>
                                                <span className={`ml-2 text-xs rounded-full px-2 py-0.5 ${isDark ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-700'}`}>
                                                    {groups[g].length} monitors
                                                </span>
                                                <span className={`ml-2 text-xs rounded-full px-2 py-0.5 ${statusLightClass}`}>
                                                    {online}/{total} online
                                                </span>
                                            </div>
                                        </button>
                                        {isOpen && (
                                            <div className="p-2 space-y-2">
                                                {groups[g].map((m) => (
                                                    <MonitorDetailCard
                                                        key={m.monitor_id}
                                                        monitorName={m.name || m.monitor_id}
                                                        monitorStatus={monitorStatusMap[m.monitor_id]}
                                                        inboundInfo={monitorInbound[m.monitor_id] || {}}
                                                        inboundAgg={monitorAggs[m.monitor_id]}
                                                        isExpanded={expandedMonitors.has(m.monitor_id)}
                                                        onToggle={() => toggleMonitor(m.monitor_id)}
                                                        useUnifiedLayout={useUnifiedLayout}
                                                    />
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                )
            })()}
        </div>
    )
}
