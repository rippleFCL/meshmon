import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { meshmonApi } from '../api'
import { useRefresh } from '../contexts/RefreshContext'
import {
    NetworkAnalysis,
    NodeAnalysis,
    NodeConnectionDetail
} from '../types'
import { useTheme } from '../contexts/ThemeContext'

interface ConnectionListProps {
    title: string
    connections: { [nodeId: string]: NodeConnectionDetail }
    averageRtt: number
    onlineCount: number
    totalCount: number
    status: string
}

interface NodeDetailCardProps {
    nodeId: string
    node: NodeAnalysis
    isExpanded: boolean
    onToggle: () => void
    useUnifiedLayout: boolean
}

const getStatusColor = (status: string) => {
    switch (status) {
        case 'online':
            return 'status-online'
        case 'offline':
            return 'status-offline'
        case 'degraded':
            return 'status-warning'
        case 'unknown':
            return 'text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800'
        case 'node_down':
            return 'text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800'
        default:
            return 'text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800'
    }
}

const getConnectionStatusColor = (onlineCount: number, totalCount: number) => {
    if (onlineCount === totalCount) {
        return 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30'
    }
    if (onlineCount === 0) {
        return 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30'
    }
    return 'text-yellow-600 dark:text-yellow-400 bg-yellow-100 dark:bg-yellow-900/30'
}

const ConnectionList: React.FC<ConnectionListProps> = ({
    title,
    connections,
    averageRtt,
    onlineCount,
    totalCount,
    status
}) => {
    const { isDark } = useTheme()

    const getDescription = (title: string) => {
        if (title === "Incoming Connections") {
            return "Nodes that can reach this node"
        }
        return "Nodes this node can reach"
    }

    return (
        <div className={`mt-2 border rounded-lg p-3 ${isDark ? 'border-gray-600' : 'border-gray-200'}`}>
            <div className="flex items-center justify-between mb-2">
                <div>
                    <h5 className={`font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{title}</h5>
                    <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        {getDescription(title)}
                    </p>
                </div>
                <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(status)}`}>
                        {status}
                    </span>
                    <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        {onlineCount}/{totalCount} reachable
                    </span>
                </div>
            </div>

            {totalCount > 0 && (
                <div className={`mb-2 text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Average response time: {averageRtt.toFixed(2)}ms
                </div>
            )}

            <div className="space-y-1">
                {Object.entries(connections).map(([targetNodeId, connection]) => (
                    <div key={targetNodeId} className={`flex items-center justify-between py-2 px-3 rounded ${isDark ? 'bg-gray-700' : 'bg-gray-50'
                        }`}>
                        <span className={`font-medium text-sm ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{targetNodeId}</span>
                        <div className="flex items-center space-x-2">
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(connection.status)}`}>
                                {connection.status === 'node_down' ? 'node down' : connection.status}
                            </span>
                            <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                                {connection.rtt > 0 ? `${connection.rtt.toFixed(2)}ms` : 'N/A'}
                            </span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}

const NodeDetailCard: React.FC<NodeDetailCardProps> = ({ nodeId, node, isExpanded, onToggle, useUnifiedLayout }) => {
    const { isDark } = useTheme()
    const avgInboundRtt = node.inbound_status.average_rtt || 0
    const avgOutboundRtt = node.outbound_status.average_rtt || 0
    const avgRtt = (avgInboundRtt + avgOutboundRtt) / 2

    const renderConnectionContent = () => {
        if (useUnifiedLayout) {
            // Unified layout
            return (
                <>
                    {/* Unified Connection List */}
                    <div className={`border rounded-lg p-3 ${isDark ? 'border-gray-600' : 'border-gray-200'}`}>
                        <div className="flex items-center justify-between mb-3">
                            <h5 className={`font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>Node Connections</h5>
                            <div className="flex items-center space-x-4 text-xs">
                                <div className="flex items-center space-x-1">
                                    <span className={`w-2 h-2 rounded-full bg-green-500`}></span>
                                    <span className={`${isDark ? 'text-gray-400' : 'text-gray-600'}`}>↔ Bidirectional</span>
                                </div>
                                <div className="flex items-center space-x-1">
                                    <span className={`w-2 h-2 rounded-full bg-yellow-500`}></span>
                                    <span className={`${isDark ? 'text-gray-400' : 'text-gray-600'}`}>→ Partial connection</span>
                                </div>
                                <div className="flex items-center space-x-1">
                                    <span className={`w-2 h-2 rounded-full bg-red-500`}></span>
                                    <span className={`${isDark ? 'text-gray-400' : 'text-gray-600'}`}>✕ No connection</span>
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2">
                            {(() => {
                                // Create a unified list of all connections
                                const allNodes = new Set([
                                    ...Object.keys(node.inbound_info),
                                    ...Object.keys(node.outbound_info)
                                ])

                                const connectionData = Array.from(allNodes).map(targetNodeId => {
                                    const inbound = node.inbound_info[targetNodeId]
                                    const outbound = node.outbound_info[targetNodeId]

                                    // Determine connection type and status
                                    const hasInbound = !!inbound && inbound.status === 'online'
                                    const hasOutbound = !!outbound && outbound.status === 'online'
                                    const isBidirectional = hasInbound && hasOutbound

                                    let connectionType = ''
                                    let connectionColor = ''
                                    let rttText = ''
                                    let sortOrder = 0

                                    if (isBidirectional) {
                                        connectionType = '↔'
                                        connectionColor = 'border-green-500 bg-green-50 dark:bg-green-900/20'
                                        const avgRtt = ((inbound.rtt + outbound.rtt) / 2)
                                        rttText = avgRtt > 0 ? `${avgRtt.toFixed(1)}ms avg` : 'N/A'
                                        sortOrder = 1
                                    } else if (hasOutbound) {
                                        connectionType = '→'
                                        connectionColor = 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20'
                                        rttText = outbound.rtt > 0 ? `${outbound.rtt.toFixed(1)}ms` : 'N/A'
                                        sortOrder = 2
                                    } else if (hasInbound) {
                                        connectionType = '←'
                                        connectionColor = 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20'
                                        rttText = inbound.rtt > 0 ? `${inbound.rtt.toFixed(1)}ms` : 'N/A'
                                        sortOrder = 3
                                    } else {
                                        connectionType = '✕'
                                        connectionColor = 'border-red-500 bg-red-50 dark:bg-red-900/20'
                                        rttText = 'N/A'
                                        sortOrder = 4
                                    }

                                    return {
                                        targetNodeId,
                                        connectionType,
                                        connectionColor,
                                        rttText,
                                        sortOrder,
                                        isBidirectional,
                                        inbound,
                                        outbound
                                    }
                                })

                                // Sort by connection type (sortOrder), then by node name
                                const sortedConnections = connectionData.sort((a, b) => {
                                    if (a.sortOrder !== b.sortOrder) {
                                        return a.sortOrder - b.sortOrder
                                    }
                                    return a.targetNodeId.localeCompare(b.targetNodeId)
                                })

                                return sortedConnections.map(({ targetNodeId, connectionType, connectionColor, rttText, isBidirectional, inbound, outbound }) => {
                                    return (
                                        <div key={targetNodeId} className={`border-2 rounded p-1.5 ${connectionColor} ${isDark ? 'bg-gray-800' : 'bg-white'} shadow-sm`}>
                                            <div className="flex items-center justify-between mb-0.5">
                                                <h6 className={`text-sm font-semibold ${isDark ? 'text-gray-100' : 'text-gray-900'} truncate pr-1`}>
                                                    {nodeId} {connectionType} {targetNodeId}
                                                </h6>
                                                <div className={`text-lg ${isDark ? 'text-gray-300' : 'text-gray-700'} flex-shrink-0`}>
                                                    {connectionType}
                                                </div>
                                            </div>
                                            <div className="space-y-0">
                                                {isBidirectional ? (
                                                    <>
                                                        <div className={`text-xs ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                                                            {nodeId} → {targetNodeId}: <span className="font-mono font-medium">{outbound?.rtt?.toFixed(1) || 'N/A'}ms</span>
                                                        </div>
                                                        <div className={`text-xs ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                                                            {targetNodeId} → {nodeId}: <span className="font-mono font-medium">{inbound?.rtt?.toFixed(1) || 'N/A'}ms</span>
                                                        </div>
                                                    </>
                                                ) : connectionType === '→' ? (
                                                    <div className={`text-xs ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                                                        {nodeId} → {targetNodeId}: <span className="font-mono font-medium">{rttText}</span>
                                                    </div>
                                                ) : connectionType === '←' ? (
                                                    <div className={`text-xs ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                                                        {targetNodeId} → {nodeId}: <span className="font-mono font-medium">{rttText}</span>
                                                    </div>
                                                ) : (
                                                    <div className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>No connection available</div>
                                                )}
                                            </div>
                                        </div>
                                    )
                                })
                            })()}
                        </div>
                    </div>
                </>
            )
        } else {
            // Traditional two-table layout
            return (
                <>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                        <ConnectionList
                            title="Incoming Connections"
                            connections={node.inbound_info}
                            averageRtt={node.inbound_status.average_rtt}
                            onlineCount={node.inbound_status.online_connections}
                            totalCount={node.inbound_status.total_connections}
                            status={node.inbound_status.status}
                        />

                        <ConnectionList
                            title="Outgoing Connections"
                            connections={node.outbound_info}
                            averageRtt={node.outbound_status.average_rtt}
                            onlineCount={node.outbound_status.online_connections}
                            totalCount={node.outbound_status.total_connections}
                            status={node.outbound_status.status}
                        />
                    </div>
                </>
            )
        }
    }

    return (
        <div className="card p-2">
            <div
                className={`flex items-center justify-between cursor-pointer py-1 px-2 rounded-lg transition-colors duration-200 ${isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50'
                    }`}
                onClick={onToggle}
            >
                <div className="flex items-center space-x-3">
                    <span className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                        {isExpanded ? '▼' : '▶'}
                    </span>
                    <h4 className={`text-base font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{nodeId}</h4>
                </div>

                <div className={`flex items-center gap-6 text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Status</div>
                        <div className={`px-2 py-0.5 text-xs font-medium rounded-full ${getStatusColor(node.node_status)}`}>
                            {node.node_status}
                        </div>
                    </div>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Ping</div>
                        <div className="font-mono text-sm">{avgRtt.toFixed(1)}ms</div>
                    </div>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Receives</div>
                        <div className={`px-2 py-0.5 text-xs font-medium rounded-full ${getConnectionStatusColor(node.inbound_status.online_connections, node.inbound_status.total_connections)}`}>
                            {node.inbound_status.online_connections}/{node.inbound_status.total_connections}
                        </div>
                    </div>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Sends to</div>
                        <div className={`px-2 py-0.5 text-xs font-medium rounded-full ${getConnectionStatusColor(node.outbound_status.online_connections, node.outbound_status.total_connections)}`}>
                            {node.outbound_status.online_connections}/{node.outbound_status.total_connections}
                        </div>
                    </div>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Version</div>
                        <div className={`text-xs px-1.5 py-0.5 rounded ${isDark ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-700'}`}>
                            {node.node_info.version}
                        </div>
                    </div>
                </div>
            </div>

            {isExpanded && (
                <div className="mt-3">
                    {renderConnectionContent()}
                </div>
            )}
        </div>
    )
}

export default function NetworkDetail() {
    const { networkId } = useParams<{ networkId: string }>()
    const navigate = useNavigate()
    const { isDark } = useTheme()
    const { registerRefreshCallback } = useRefresh()
    const [network, setNetwork] = useState<NetworkAnalysis | null>(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())
    const [useUnifiedLayout, setUseUnifiedLayout] = useState(true)

    const fetchData = async (isInitialLoad = false) => {
        try {
            if (isInitialLoad) {
                setLoading(true)
            } else {
                setRefreshing(true)
            }

            const response = await meshmonApi.getViewData()

            if (networkId && response.data.networks[networkId]) {
                setNetwork(response.data.networks[networkId])
                setError(null)
            } else {
                setError(`Network "${networkId}" not found`)
            }
        } catch (err) {
            setError('Failed to fetch network data')
            console.error('Error fetching data:', err)
        } finally {
            if (isInitialLoad) {
                setLoading(false)
            } else {
                setRefreshing(false)
            }
        }
    }

    useEffect(() => {
        const fetchData = async (isInitialLoad = false) => {
            try {
                if (isInitialLoad) {
                    setLoading(true)
                } else {
                    setRefreshing(true)
                }

                const response = await meshmonApi.getViewData()

                if (networkId && response.data.networks[networkId]) {
                    setNetwork(response.data.networks[networkId])
                    setError(null)
                } else {
                    setError(`Network "${networkId}" not found`)
                }
            } catch (err) {
                setError('Failed to fetch network data')
                console.error('Error fetching data:', err)
            } finally {
                if (isInitialLoad) {
                    setLoading(false)
                } else {
                    setRefreshing(false)
                }
            }
        }

        const handleRefresh = () => fetchData(false)

        fetchData(true) // Initial load
        const cleanup = registerRefreshCallback(handleRefresh) // Register refresh callback

        const interval = setInterval(() => fetchData(false), 10000) // Background refresh every 10 seconds

        return () => {
            clearInterval(interval)
            cleanup()
        }
    }, [networkId, registerRefreshCallback])

    const toggleNode = (nodeId: string) => {
        const newExpanded = new Set(expandedNodes)
        if (newExpanded.has(nodeId)) {
            newExpanded.delete(nodeId)
        } else {
            newExpanded.add(nodeId)
        }
        setExpandedNodes(newExpanded)
    }

    const expandAll = () => {
        if (network) {
            setExpandedNodes(new Set(Object.keys(network.node_analyses)))
        }
    }

    const collapseAll = () => {
        setExpandedNodes(new Set())
    }

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="flex items-center space-x-4">
                    <button
                        onClick={() => navigate('/networks')}
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
                        onClick={() => navigate('/networks')}
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

    const networkStatus = network.offline_nodes === 0 ? 'Healthy' :
        network.online_nodes > 0 ? 'Degraded' : 'Offline'

    const statusColor = network.offline_nodes === 0 ? 'text-green-600 bg-green-100' :
        network.online_nodes > 0 ? 'text-yellow-600 bg-yellow-100' :
            'text-red-600 bg-red-100'

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                    <button
                        onClick={() => navigate('/networks')}
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
                        <div className={`text-3xl font-bold mb-2 ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{network.total_nodes}</div>
                        <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Total Nodes</div>
                    </div>
                    <div className={`text-center p-6 rounded-lg flex flex-col justify-center stats-update ${isDark ? 'bg-green-900/20' : 'bg-green-50'}`}>
                        <div className={`text-3xl font-bold mb-2 ${isDark ? 'text-green-400' : 'text-green-600'}`}>{network.online_nodes}</div>
                        <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Online Nodes</div>
                    </div>
                    <div className={`text-center p-6 rounded-lg flex flex-col justify-center stats-update ${isDark ? 'bg-red-900/20' : 'bg-red-50'}`}>
                        <div className={`text-3xl font-bold mb-2 ${isDark ? 'text-red-400' : 'text-red-600'}`}>{network.offline_nodes}</div>
                        <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Offline Nodes</div>
                    </div>
                    <div className={`text-center p-6 rounded-lg flex flex-col justify-center stats-update ${isDark ? 'bg-blue-900/20' : 'bg-blue-50'}`}>
                        <div className={`text-xl font-bold mb-2 ${isDark ? 'text-blue-400' : 'text-blue-600'} leading-tight`}>
                            {(() => {
                                const oldestDate = Object.values(network.node_analyses).reduce((oldest, node) => {
                                    const nodeDate = new Date(node.node_info.data_retention)
                                    return nodeDate < oldest ? nodeDate : oldest
                                }, new Date())

                                try {
                                    return oldestDate.toLocaleString('en-US', {
                                        year: 'numeric',
                                        month: 'short',
                                        day: 'numeric',
                                        hour: '2-digit',
                                        minute: '2-digit',
                                        hour12: false
                                    }).replace(/,/g, '')
                                } catch {
                                    return 'N/A'
                                }
                            })()}
                        </div>
                        <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>Data Retained From</div>
                    </div>
                </div>
            </div>

            {/* Node Details */}
            <div className="data-fade">
                <h3 className="text-lg font-medium text-gray-100 mb-3">Node Details</h3>
                <div className="space-y-2">
                    {Object.entries(network.node_analyses).map(([nodeId, node]) => (
                        <NodeDetailCard
                            key={nodeId}
                            nodeId={nodeId}
                            node={node}
                            isExpanded={expandedNodes.has(nodeId)}
                            onToggle={() => toggleNode(nodeId)}
                            useUnifiedLayout={useUnifiedLayout}
                        />
                    ))}
                </div>
            </div>
        </div>
    )
}
