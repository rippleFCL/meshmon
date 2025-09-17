import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Network, Server, Activity, AlertTriangle } from 'lucide-react'
import { meshmonApi } from '../api'
import { MultiNetworkAnalysis } from '../types'
import { useTheme } from '../contexts/ThemeContext'
import { useRefresh } from '../contexts/RefreshContext'

interface DashboardStats {
    totalNetworks: number
    totalNodes: number
    avgLatency: number
    alertCount: number
}

export default function Dashboard() {
    const navigate = useNavigate()
    const { isDark } = useTheme()
    const { registerRefreshCallback } = useRefresh()
    const [stats, setStats] = useState<DashboardStats>({
        totalNetworks: 0,
        totalNodes: 0,
        avgLatency: 0,
        alertCount: 0
    })
    const [viewData, setViewData] = useState<MultiNetworkAnalysis | null>(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const fetchData = async (isInitialLoad = false) => {
            try {
                if (isInitialLoad) {
                    setLoading(true)
                } else {
                    setRefreshing(true)
                }

                const response = await meshmonApi.getViewData()
                const data = response.data
                setViewData(data)

                // Calculate stats from the new data structure
                const networks = Object.keys(data.networks)
                let totalNodes = 0
                let totalLatency = 0
                let latencyCount = 0
                let alertCount = 0

                networks.forEach(networkId => {
                    const network = data.networks[networkId]
                    totalNodes += network.total_nodes
                    alertCount += network.offline_nodes

                    // Calculate average latency from all connections
                    Object.values(network.node_analyses).forEach(node => {
                        // Add inbound connection latencies
                        Object.values(node.inbound_info).forEach(connection => {
                            if (connection.status === 'online') {
                                totalLatency += connection.rtt
                                latencyCount++
                            }
                        })

                        // Add outbound connection latencies
                        Object.values(node.outbound_info).forEach(connection => {
                            if (connection.status === 'online') {
                                totalLatency += connection.rtt
                                latencyCount++
                            }
                        })
                    })
                })

                setStats({
                    totalNetworks: networks.length,
                    totalNodes,
                    avgLatency: latencyCount > 0 ? Math.round(totalLatency / latencyCount) : 0,
                    alertCount
                })

                setError(null)
            } catch (err) {
                setError('Failed to fetch network data')
                console.error('Failed to fetch data:', err)
            } finally {
                if (isInitialLoad) {
                    setLoading(false)
                } else {
                    setRefreshing(false)
                }
            }
        }

        const handleRefresh = () => fetchData(false)

        // Initial load
        fetchData(true)

        // Register refresh callback and get cleanup function
        const cleanup = registerRefreshCallback(handleRefresh)

        // Refresh data every 10 seconds (background updates)
        const interval = setInterval(() => fetchData(false), 10000)

        return () => {
            clearInterval(interval)
            cleanup()
        }
    }, [registerRefreshCallback])

    if (loading) {
        return (
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
                    <p className="text-gray-600">Loading network data...</p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
                    <p className="text-red-600">{error}</p>
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>Dashboard</h1>
                    <p className={`${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Overview of your mesh network status</p>
                </div>
                {refreshing && (
                    <div className={`flex items-center space-x-2 text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
                        <span>Updating...</span>
                    </div>
                )}
            </div>

            {/* Stats Grid - top row, 4 cards in a line */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <div className="card p-6 stats-update">
                    <div className="flex items-center">
                        <div className={`p-3 rounded-lg ${isDark ? 'bg-blue-900' : 'bg-primary-100'}`}>
                            <Network className={`h-6 w-6 ${isDark ? 'text-blue-400' : 'text-primary-600'}`} />
                        </div>
                        <div className="ml-4">
                            <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{stats.totalNetworks}</p>
                            <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Networks</p>
                        </div>
                    </div>
                </div>

                <div className="card p-6 stats-update">
                    <div className="flex items-center">
                        <div className={`p-3 rounded-lg ${isDark ? 'bg-blue-900' : 'bg-blue-100'}`}>
                            <Server className={`h-6 w-6 ${isDark ? 'text-blue-400' : 'text-blue-600'}`} />
                        </div>
                        <div className="ml-4">
                            <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{stats.totalNodes}</p>
                            <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Active Nodes</p>
                        </div>
                    </div>
                </div>

                <div className="card p-6 stats-update">
                    <div className="flex items-center">
                        <div className={`p-3 rounded-lg ${isDark ? 'bg-green-900' : 'bg-green-100'}`}>
                            <Activity className={`h-6 w-6 ${isDark ? 'text-green-400' : 'text-green-600'}`} />
                        </div>
                        <div className="ml-4">
                            <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{stats.avgLatency}ms</p>
                            <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Avg Latency</p>
                        </div>
                    </div>
                </div>

                <div className="card p-6 stats-update">
                    <div className="flex items-center">
                        <div className={`p-3 rounded-lg ${isDark ? 'bg-red-900' : 'bg-red-100'}`}>
                            <AlertTriangle className={`h-6 w-6 ${isDark ? 'text-red-400' : 'text-red-600'}`} />
                        </div>
                        <div className="ml-4">
                            <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{stats.alertCount}</p>
                            <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Alerts</p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Networks Section - full width, auto height */}
            <div className="card p-6 w-full data-fade">
                <h3 className={`text-lg font-medium mb-4 ${isDark ? 'text-white' : 'text-gray-900'}`}>Networks</h3>
                <div className="flex flex-wrap gap-3">
                    {viewData && Object.entries(viewData.networks).map(([networkId, network]) => {
                        const status = network.offline_nodes === 0 ? 'online' :
                            network.online_nodes > 0 ? 'warning' : 'offline'
                        const statusClass = status === 'online' ? 'status-online' :
                            status === 'offline' ? 'status-offline' : 'status-warning'

                        return (
                            <div
                                key={networkId}
                                className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all duration-200 min-w-64 flex-1 ${isDark
                                    ? 'bg-gray-700 hover:bg-gray-600'
                                    : 'bg-gray-50 hover:bg-gray-100'
                                    } hover:shadow-md`}
                                onClick={() => navigate(`/networks/${networkId}`)}
                            >
                                <div>
                                    <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>{networkId}</span>
                                    <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'} mt-1`}>
                                        {network.online_nodes}/{network.total_nodes} nodes online
                                    </p>
                                </div>
                                <span className={`px-3 py-1 text-xs font-medium rounded-full ${statusClass}`}>
                                    {status.charAt(0).toUpperCase() + status.slice(1)}
                                </span>
                            </div>
                        )
                    })}
                </div>
            </div>

            {/* Node Information Section - Full width */}
            <div className="card p-6 data-fade">
                <h3 className={`text-lg font-medium mb-4 ${isDark ? 'text-white' : 'text-gray-900'}`}>Node Information</h3>
                <div className="space-y-3">
                    {viewData && Object.entries(viewData.networks).map(([networkId, network]) => {
                        return Object.entries(network.node_analyses).map(([nodeId, node]) => {
                            const avgInboundRtt = node.inbound_status.average_rtt || 0
                            const avgOutboundRtt = node.outbound_status.average_rtt || 0
                            const avgRtt = (avgInboundRtt + avgOutboundRtt) / 2

                            return (
                                <div key={`${networkId}-${nodeId}`} className={`flex items-center space-x-3 p-3 rounded-lg transition-all duration-200 hover:shadow-sm ${isDark ? 'bg-gray-700' : 'bg-gray-50'
                                    }`}>
                                    <div className={`w-2 h-2 rounded-full transition-colors duration-200 ${node.node_status === 'online' ? 'bg-green-500' : 'bg-red-500'
                                        }`}></div>
                                    <div className="flex-1">
                                        <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>{nodeId} ({networkId})</p>
                                        <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                            {node.node_status} • Avg RTT: {avgRtt.toFixed(1)}ms
                                        </p>
                                    </div>
                                    <div className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                        In: {node.inbound_status.online_connections}/{node.inbound_status.total_connections} •
                                        Out: {node.outbound_status.online_connections}/{node.outbound_status.total_connections}
                                    </div>
                                </div>
                            )
                        })
                    }).flat()}
                </div>
            </div>
        </div>
    )
}
