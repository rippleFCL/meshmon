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
            return 'status-offline'
        default:
            return 'text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800'
    }
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

    return (
        <div className={`mt-2 border rounded-lg p-3 ${isDark ? 'border-gray-600' : 'border-gray-200'}`}>
            <div className="flex items-center justify-between mb-2">
                <h5 className={`font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{title}</h5>
                <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(status)}`}>
                        {status}
                    </span>
                    <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        {onlineCount}/{totalCount} online
                    </span>
                </div>
            </div>

            {totalCount > 0 && (
                <div className={`mb-2 text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Average RTT: {averageRtt.toFixed(2)}ms
                </div>
            )}

            <div className="space-y-1">
                {Object.entries(connections).map(([targetNodeId, connection]) => (
                    <div key={targetNodeId} className={`flex items-center justify-between py-2 px-3 rounded ${isDark ? 'bg-gray-700' : 'bg-gray-50'
                        }`}>
                        <span className={`font-medium text-sm ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{targetNodeId}</span>
                        <div className="flex items-center space-x-2">
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(connection.status)}`}>
                                {connection.status}
                            </span>
                            <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{connection.rtt.toFixed(2)}ms</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}

const NodeDetailCard: React.FC<NodeDetailCardProps> = ({ nodeId, node, isExpanded, onToggle }) => {
    const { isDark } = useTheme()
    const avgInboundRtt = node.inbound_status.average_rtt || 0
    const avgOutboundRtt = node.outbound_status.average_rtt || 0
    const avgRtt = (avgInboundRtt + avgOutboundRtt) / 2

    // Determine connection status based on inbound and outbound
    const getConnectionStatus = () => {
        const inboundStatus = node.inbound_status.status
        const outboundStatus = node.outbound_status.status

        if (inboundStatus === 'degraded' || outboundStatus === 'degraded') {
            return 'degraded'
        }
        if (inboundStatus === 'offline' || outboundStatus === 'offline') {
            return 'offline'
        }
        if (inboundStatus === 'online' && outboundStatus === 'online') {
            return 'online'
        }
        return 'unknown'
    }

    const connectionStatus = getConnectionStatus()

    const formatDataRetention = (dateString: string) => {
        try {
            const date = new Date(dateString)
            return date.toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                hour12: false
            }).replace(/,/g, '')
        } catch {
            return dateString
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
                    <div className="text-center">
                        <div className="font-medium">Node</div>
                        <div className={`px-2 py-0.5 text-xs font-medium rounded-full ${getStatusColor(node.node_status)}`}>
                            {node.node_status}
                        </div>
                    </div>
                    <div className="text-center">
                        <div className="font-medium">Conn</div>
                        <div className={`px-2 py-0.5 text-xs font-medium rounded-full ${getStatusColor(connectionStatus)}`}>
                            {connectionStatus}
                        </div>
                    </div>
                    <div className="text-center">
                        <div className="font-medium">RTT</div>
                        <div className="font-mono text-sm">{avgRtt.toFixed(1)}ms</div>
                    </div>
                    <div className="text-center">
                        <div className="font-medium">In</div>
                        <div className="font-mono text-sm">{node.inbound_status.online_connections}/{node.inbound_status.total_connections}</div>
                    </div>
                    <div className="text-center">
                        <div className="font-medium">Out</div>
                        <div className="font-mono text-sm">{node.outbound_status.online_connections}/{node.outbound_status.total_connections}</div>
                    </div>
                    <div className="text-center">
                        <div className="font-medium">Ver</div>
                        <div className={`text-xs px-1.5 py-0.5 rounded ${isDark ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-700'}`}>
                            {node.node_info.version}
                        </div>
                    </div>
                </div>
            </div>

            {isExpanded && (
                <div className="mt-3">
                    {/* Data Retained Since */}
                    <div className={`mb-3 px-2 py-2 rounded ${isDark ? 'bg-gray-700' : 'bg-gray-50'}`}>
                        <div className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                            <span>Data retained since: </span>
                            <span className={`font-mono ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                                {formatDataRetention(node.node_info.data_retention)}
                            </span>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                        <ConnectionList
                            title="Inbound Connections"
                            connections={node.inbound_info}
                            averageRtt={node.inbound_status.average_rtt}
                            onlineCount={node.inbound_status.online_connections}
                            totalCount={node.inbound_status.total_connections}
                            status={node.inbound_status.status}
                        />

                        <ConnectionList
                            title="Outbound Connections"
                            connections={node.outbound_info}
                            averageRtt={node.outbound_status.average_rtt}
                            onlineCount={node.outbound_status.online_connections}
                            totalCount={node.outbound_status.total_connections}
                            status={node.outbound_status.status}
                        />
                    </div>
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
                        />
                    ))}
                </div>
            </div>
        </div>
    )
}
