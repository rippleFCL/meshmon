import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, BellRing, CheckCircle2, Clock3, Users } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import { useRefresh } from '../contexts/RefreshContext'
import { notificationApi } from '../api/notificationCluster'
import type { NotificationClusterApi, NotificationClusterStatusEnum } from '../types/notificationCluster'

export default function NotificationClusterPage() {
    const { isDark } = useTheme()
    const { registerRefreshCallback } = useRefresh()
    const [data, setData] = useState<NotificationClusterApi | null>(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const load = async (initial = false) => {
            try {
                if (initial) setLoading(true)
                else setRefreshing(true)
                const res = await notificationApi.getCluster()
                setData(res.data)
                setError(null)
            } catch (e) {
                console.error(e)
                setError('Failed to fetch notification cluster')
            } finally {
                if (initial) setLoading(false)
                else setRefreshing(false)
            }
        }

        const doRefresh = () => load(false)
        load(true)
        const cleanup = registerRefreshCallback(doRefresh)
        const interval = setInterval(() => load(false), 10000)
        return () => { clearInterval(interval); cleanup() }
    }, [registerRefreshCallback])

    const statusColor = (s: NotificationClusterStatusEnum) => {
        switch (s) {
            case 'LEADER':
                return 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
            case 'FOLLOWER':
                return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
            case 'WAITING_FOR_CONSENSUS':
                return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
            case 'NOT_PARTICIPATING':
            default:
                return 'bg-gray-100 text-gray-700 dark:bg-gray-700/60 dark:text-gray-300'
        }
    }

    const summary = useMemo(() => {
        if (!data) return null
        let networks = 0
        let clusters = 0
        let nodes = 0
        for (const [_, nc] of Object.entries(data.networks)) {
            networks++
            clusters += Object.keys(nc.clusters).length
            for (const [__, c] of Object.entries(nc.clusters)) {
                nodes += Object.keys(c.node_statuses).length
            }
        }
        return { networks, clusters, nodes }
    }, [data])

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>Notification Cluster</h1>
                    <p className={`${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Status and metadata for the notification cluster</p>
                </div>
                {refreshing && (
                    <div className={`flex items-center space-x-2 text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
                        <span>Updating...</span>
                    </div>
                )}
            </div>

            {loading && (
                <div className="card p-6">
                    <div className="flex items-center space-x-3 text-gray-600 dark:text-gray-300">
                        <BellRing className="h-5 w-5" />
                        <span>Loading notification cluster...</span>
                    </div>
                </div>
            )}

            {error && (
                <div className="card p-6 border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300">
                    <div className="flex items-center space-x-2">
                        <AlertCircle className="h-5 w-5" />
                        <span>{error}</span>
                    </div>
                </div>
            )}

            {!loading && !error && data && (
                <>
                    {/* Summary cards */}
                    {summary && (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            <div className="card p-5 flex items-center justify-between">
                                <div>
                                    <div className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Networks</div>
                                    <div className={`text-2xl font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{summary.networks}</div>
                                </div>
                                <Users className={`h-8 w-8 ${isDark ? 'text-gray-300' : 'text-gray-500'}`} />
                            </div>
                            <div className="card p-5 flex items-center justify-between">
                                <div>
                                    <div className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Clusters</div>
                                    <div className={`text-2xl font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{summary.clusters}</div>
                                </div>
                                <CheckCircle2 className={`h-8 w-8 ${isDark ? 'text-gray-300' : 'text-gray-500'}`} />
                            </div>
                            <div className="card p-5 flex items-center justify-between">
                                <div>
                                    <div className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Nodes</div>
                                    <div className={`text-2xl font-semibold ${isDark ? 'text-white' : 'text-gray-900'}`}>{summary.nodes}</div>
                                </div>
                                <Clock3 className={`h-8 w-8 ${isDark ? 'text-gray-300' : 'text-gray-500'}`} />
                            </div>
                        </div>
                    )}

                    {/* Networks -> Clusters breakdown */}
                    {Object.entries(data.networks).map(([networkId, clusters]) => (
                        <div key={networkId} className="card p-6 data-fade">
                            <h3 className={`text-lg font-medium mb-4 ${isDark ? 'text-white' : 'text-gray-900'}`}>Network: {networkId}</h3>

                            {Object.entries(clusters.clusters).length === 0 ? (
                                <p className={`${isDark ? 'text-gray-400' : 'text-gray-600'}`}>No notification clusters found.</p>) : (
                                <div className="space-y-5">
                                    {Object.entries(clusters.clusters).map(([clusterName, cluster]) => {
                                        const entries = Object.entries(cluster.node_statuses)
                                        const counts = entries.reduce((acc, [_, st]) => {
                                            acc.total++
                                            acc[st] = (acc[st] || 0) + 1
                                            return acc
                                        }, { total: 0 } as Record<string, number>)

                                        return (
                                            <div key={`${networkId}-${clusterName}`} className="rounded-lg border border-gray-200 dark:border-gray-600">
                                                <div className={`px-4 py-3 flex items-center justify-between ${isDark ? 'bg-gray-800' : 'bg-gray-50'}`}>
                                                    <div className="flex items-center gap-3">
                                                        <BellRing className={`h-5 w-5 ${isDark ? 'text-gray-300' : 'text-gray-600'}`} />
                                                        <div>
                                                            <div className={`font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>{clusterName}</div>
                                                            <div className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{counts.total} nodes</div>
                                                        </div>
                                                    </div>
                                                    <div className="flex gap-2">
                                                        {(['LEADER', 'FOLLOWER', 'WAITING_FOR_CONSENSUS', 'NOT_PARTICIPATING'] as NotificationClusterStatusEnum[])
                                                            .map((k) => (
                                                                <span key={k} className={`text-xs px-2 py-1 rounded-full ${statusColor(k)}`}>
                                                                    {k}: {counts[k as any] || 0}
                                                                </span>
                                                            ))}
                                                    </div>
                                                </div>
                                                <div className="p-4">
                                                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                                                        {entries.map(([nodeId, status]) => (
                                                            <div
                                                                key={nodeId}
                                                                className={`rounded-lg border p-4 flex items-start justify-between shadow-sm transition-colors duration-200 ${isDark ? 'border-gray-600 bg-gray-700 hover:bg-gray-600' : 'border-gray-200 bg-gray-50 hover:bg-gray-100'}`}
                                                            >
                                                                <div className="min-w-0 pr-3">
                                                                    <span className={`text-sm px-2 py-1 rounded-full whitespace-nowrap`}>{nodeId}</span>
                                                                </div>
                                                                <div className="flex-shrink-0">
                                                                    <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${statusColor(status)}`}>{status}</span>
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            )}
                        </div>
                    ))}
                </>
            )}
        </div>
    )
}
