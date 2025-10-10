import { useState, useEffect } from 'react'
import { } from 'react-router-dom'
import { Network, Server, Activity, AlertTriangle } from 'lucide-react'
import { meshmonApi } from '../api'
import { MeshMonApi } from '../types'
import { useTheme } from '../contexts/ThemeContext'
import { useRefresh } from '../contexts/RefreshContext'
import StatsCard from '../components/dashboard/StatsCard'
import NetworkItem from '../components/dashboard/NetworkItem'
import NodeInfoRow from '../components/dashboard/NodeInfoRow'

interface DashboardStats {
    totalNetworks: number
    totalNodes: number
    avgLatency: number
    alertCount: number
}

export default function Dashboard() {

    const { isDark } = useTheme()
    const { registerRefreshCallback } = useRefresh()
    const [stats, setStats] = useState<DashboardStats>({
        totalNetworks: 0,
        totalNodes: 0,
        avgLatency: 0,
        alertCount: 0
    })
    const [viewData, setViewData] = useState<MeshMonApi | null>(null)
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
                    const nodeIds = Object.keys(network.nodes)
                    totalNodes += nodeIds.length
                    alertCount += nodeIds.filter(id => network.nodes[id].status === 'offline').length

                    // Average latency from node-to-node connections (both directions)
                    for (const c of network.connections) {
                        if (c.src_node.conn_type === 'up') { totalLatency += c.src_node.rtt; latencyCount++ }
                        if (c.dest_node.conn_type === 'up') { totalLatency += c.dest_node.rtt; latencyCount++ }
                    }
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
                <StatsCard icon={<Network className="h-6 w-6" />} value={stats.totalNetworks} label="Networks" />
                <StatsCard icon={<Server className="h-6 w-6" />} value={stats.totalNodes} label="Active Nodes" iconBgClass={isDark ? 'bg-blue-900' : 'bg-blue-100'} iconColorClass={isDark ? 'text-blue-400' : 'text-blue-600'} />
                <StatsCard icon={<Activity className="h-6 w-6" />} value={`${stats.avgLatency}ms`} label="Avg Latency" iconBgClass={isDark ? 'bg-green-900' : 'bg-green-100'} iconColorClass={isDark ? 'text-green-400' : 'text-green-600'} />
                <StatsCard icon={<AlertTriangle className="h-6 w-6" />} value={stats.alertCount} label="Alerts" iconBgClass={isDark ? 'bg-red-900' : 'bg-red-100'} iconColorClass={isDark ? 'text-red-400' : 'text-red-600'} />
            </div>

            {/* Networks Section - full width, auto height */}
            <div className="card p-6 w-full data-fade">
                <h3 className={`text-lg font-medium mb-4 ${isDark ? 'text-white' : 'text-gray-900'}`}>Networks</h3>
                <div className="flex flex-wrap gap-3">
                    {viewData && Object.entries(viewData.networks).map(([networkId, network]) => (
                        <NetworkItem key={networkId} networkId={networkId} network={network} />
                    ))}
                </div>
            </div>

            {/* Node Information Section - Full width */}
            <div className="card p-6 data-fade">
                <h3 className={`text-lg font-medium mb-4 ${isDark ? 'text-white' : 'text-gray-900'}`}>Node Information</h3>
                <div className="space-y-3">
                    {viewData && Object.entries(viewData.networks).map(([networkId, network]) => {
                        const nodeIds = Object.keys(network.nodes)
                        const metrics: Record<string, { inTotal: number; inOnline: number; inRttSum: number; inRttCount: number; outTotal: number; outOnline: number; outRttSum: number; outRttCount: number; status: string }>
                            = Object.fromEntries(nodeIds.map(id => [id, { inTotal: 0, inOnline: 0, inRttSum: 0, inRttCount: 0, outTotal: 0, outOnline: 0, outRttSum: 0, outRttCount: 0, status: network.nodes[id].status }]))

                        for (const c of network.connections) {
                            const s = c.src_node, d = c.dest_node
                            // s -> d
                            metrics[d.name].inTotal++
                            metrics[s.name].outTotal++
                            if (s.conn_type === 'up') { metrics[d.name].inOnline++; metrics[s.name].outOnline++; metrics[d.name].inRttSum += s.rtt; metrics[d.name].inRttCount++; metrics[s.name].outRttSum += s.rtt; metrics[s.name].outRttCount++ }
                            // d -> s
                            metrics[s.name].inTotal++
                            metrics[d.name].outTotal++
                            if (d.conn_type === 'up') { metrics[s.name].inOnline++; metrics[d.name].outOnline++; metrics[s.name].inRttSum += d.rtt; metrics[s.name].inRttCount++; metrics[d.name].outRttSum += d.rtt; metrics[d.name].outRttCount++ }
                        }

                        return nodeIds.map(nodeId => {
                            const m = metrics[nodeId]
                            const avgInboundRtt = m.inRttCount > 0 ? m.inRttSum / m.inRttCount : 0
                            const avgOutboundRtt = m.outRttCount > 0 ? m.outRttSum / m.outRttCount : 0
                            const avgRtt = (avgInboundRtt + avgOutboundRtt) / 2
                            return (
                                <NodeInfoRow
                                    key={`${networkId}-${nodeId}`}
                                    networkId={networkId}
                                    nodeId={nodeId}
                                    status={m.status as any}
                                    avgRtt={avgRtt}
                                    inOnline={m.inOnline}
                                    inTotal={m.inTotal}
                                    outOnline={m.outOnline}
                                    outTotal={m.outTotal}
                                />
                            )
                        })
                    }).flat()}
                </div>
            </div>
        </div>
    )
}
