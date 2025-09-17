import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { meshmonApi } from '../api'
import {
    NetworkAnalysis,
    NodeAnalysis,
    NodeConnectionDetail
} from '../types'

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
            return 'text-green-600 bg-green-100'
        case 'offline':
            return 'text-red-600 bg-red-100'
        case 'degraded':
            return 'text-yellow-600 bg-yellow-100'
        case 'unknown':
            return 'text-gray-600 bg-gray-100'
        case 'node_down':
            return 'text-red-800 bg-red-200'
        default:
            return 'text-gray-600 bg-gray-100'
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
    return (
        <div className="mt-4 border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
                <h5 className="font-medium text-gray-900">{title}</h5>
                <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(status)}`}>
                        {status}
                    </span>
                    <span className="text-sm text-gray-600">
                        {onlineCount}/{totalCount} online
                    </span>
                </div>
            </div>

            {totalCount > 0 && (
                <div className="mb-3 text-sm text-gray-600">
                    Average RTT: {averageRtt.toFixed(2)}ms
                </div>
            )}

            <div className="space-y-2">
                {Object.entries(connections).map(([targetNodeId, connection]) => (
                    <div key={targetNodeId} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded">
                        <span className="font-medium text-sm">{targetNodeId}</span>
                        <div className="flex items-center space-x-2">
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(connection.status)}`}>
                                {connection.status}
                            </span>
                            <span className="text-sm text-gray-600">{connection.rtt.toFixed(2)}ms</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}

const NodeDetailCard: React.FC<NodeDetailCardProps> = ({ nodeId, node, isExpanded, onToggle }) => {
    const avgInboundRtt = node.inbound_status.average_rtt || 0
    const avgOutboundRtt = node.outbound_status.average_rtt || 0
    const avgRtt = (avgInboundRtt + avgOutboundRtt) / 2

    return (
        <div className="card p-6">
            <div
                className="flex items-center justify-between cursor-pointer"
                onClick={onToggle}
            >
                <div className="flex items-center space-x-3">
                    <span className="text-lg">
                        {isExpanded ? '▼' : '▶'}
                    </span>
                    <h4 className="text-lg font-medium text-gray-900">{nodeId}</h4>
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(node.node_status)}`}>
                        {node.node_status}
                    </span>
                </div>

                <div className="flex items-center space-x-6 text-sm text-gray-600">
                    <div className="text-center">
                        <div className="font-medium">Avg RTT</div>
                        <div>{avgRtt.toFixed(1)}ms</div>
                    </div>
                    <div className="text-center">
                        <div className="font-medium">Inbound</div>
                        <div>{node.inbound_status.online_connections}/{node.inbound_status.total_connections}</div>
                    </div>
                    <div className="text-center">
                        <div className="font-medium">Outbound</div>
                        <div>{node.outbound_status.online_connections}/{node.outbound_status.total_connections}</div>
                    </div>
                </div>
            </div>

            {isExpanded && (
                <div className="mt-6">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
    const [network, setNetwork] = useState<NetworkAnalysis | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())

    const fetchData = async () => {
        try {
            setLoading(true)
            const response = await meshmonApi.getViewData()

            if (networkId && response.data.networks[networkId]) {
                setNetwork(response.data.networks[networkId])
            } else {
                setError(`Network "${networkId}" not found`)
            }

            setError(null)
        } catch (err) {
            setError('Failed to fetch network data')
            console.error('Error fetching data:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchData()
        const interval = setInterval(fetchData, 30000) // Refresh every 30 seconds
        return () => clearInterval(interval)
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
                        className="p-2 hover:bg-gray-100 rounded-lg"
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </button>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">Network Details</h1>
                        <p className="text-gray-600">Loading network data...</p>
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
                        className="p-2 hover:bg-gray-100 rounded-lg"
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </button>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">Network Details</h1>
                        <p className="text-gray-600">Network information</p>
                    </div>
                </div>
                <div className="card p-6">
                    <div className="text-red-600 text-center">
                        <p>{error || 'Network not found'}</p>
                        <button
                            onClick={fetchData}
                            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
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
                        className="p-2 hover:bg-gray-100 rounded-lg"
                    >
                        <ArrowLeft className="h-5 w-5" />
                    </button>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">{networkId}</h1>
                        <p className="text-gray-600">Detailed network monitoring and node connections</p>
                    </div>
                </div>
                <div className="flex items-center space-x-3">
                    <button
                        onClick={expandAll}
                        className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded"
                    >
                        Expand All
                    </button>
                    <button
                        onClick={collapseAll}
                        className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded"
                    >
                        Collapse All
                    </button>
                    <button
                        onClick={fetchData}
                        className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center space-x-2"
                    >
                        <RefreshCw className="h-4 w-4" />
                        <span>Refresh</span>
                    </button>
                </div>
            </div>

            {/* Network Overview */}
            <div className="card p-6">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="text-lg font-medium text-gray-900">Network Overview</h3>
                    <span className={`px-3 py-1 text-sm font-medium rounded-full ${statusColor}`}>
                        {networkStatus}
                    </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="text-center p-6 bg-gray-50 rounded-lg">
                        <div className="text-3xl font-bold text-gray-900 mb-2">{network.total_nodes}</div>
                        <div className="text-sm text-gray-600">Total Nodes</div>
                    </div>
                    <div className="text-center p-6 bg-green-50 rounded-lg">
                        <div className="text-3xl font-bold text-green-600 mb-2">{network.online_nodes}</div>
                        <div className="text-sm text-gray-600">Online Nodes</div>
                        <div className="text-xs text-gray-500 mt-1">
                            {((network.online_nodes / network.total_nodes) * 100).toFixed(1)}% uptime
                        </div>
                    </div>
                    <div className="text-center p-6 bg-red-50 rounded-lg">
                        <div className="text-3xl font-bold text-red-600 mb-2">{network.offline_nodes}</div>
                        <div className="text-sm text-gray-600">Offline Nodes</div>
                        <div className="text-xs text-gray-500 mt-1">
                            {network.offline_nodes > 0 ? 'Requires attention' : 'All systems operational'}
                        </div>
                    </div>
                </div>
            </div>

            {/* Node Details */}
            <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Node Details</h3>
                <div className="space-y-4">
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
