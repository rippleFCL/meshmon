import { useEffect, useMemo, useState } from 'react'
import { useTheme } from '../contexts/ThemeContext'
import { useRefresh } from '../contexts/RefreshContext'
import { clusterApi } from '../api/cluster'
import type { ClusterInfoApi, ClusterInfo, ClusterNodeStatusEnum } from '../types/cluster'

function badgeClass(status: ClusterNodeStatusEnum, isDark: boolean): string {
    switch (status) {
        case 'online':
            return isDark ? 'bg-green-900/30 text-green-300' : 'bg-green-100 text-green-700'
        case 'offline':
            return isDark ? 'bg-red-900/30 text-red-300' : 'bg-red-100 text-red-700'
        case 'unknown':
        default:
            return isDark ? 'bg-gray-700/60 text-gray-300' : 'bg-gray-100 text-gray-700'
    }
}

function formatTimeWithMs(iso: string): string {
    const d = new Date(iso)
    try {
        // Prefer Intl with fractional seconds if available
        // Only time components, no date
        // Use 24-hour for consistency
        // Note: fractionalSecondDigits is widely supported in modern browsers
        // Fallback provided below
        const fmt = new Intl.DateTimeFormat(undefined, {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
            fractionalSecondDigits: 3 as any,
        } as Intl.DateTimeFormatOptions)
        return fmt.format(d)
    } catch {
        const pad = (n: number, w = 2) => n.toString().padStart(w, '0')
        const hh = pad(d.getHours())
        const mm = pad(d.getMinutes())
        const ss = pad(d.getSeconds())
        const ms = pad(d.getMilliseconds(), 3)
        return `${hh}:${mm}:${ss}.${ms}`
    }
}

export default function ClusterPage() {
    const { isDark } = useTheme()
    const { registerRefreshCallback } = useRefresh()
    const [data, setData] = useState<ClusterInfoApi | null>(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const load = async (initial = false) => {
            try {
                if (initial) setLoading(true); else setRefreshing(true)
                const res = await clusterApi.getCluster()
                setData(res.data)
                setError(null)
            } catch (e) {
                console.error(e)
                setError('Failed to fetch cluster info')
            } finally {
                if (initial) setLoading(false); else setRefreshing(false)
            }
        }
        const doRefresh = () => load(false)
        load(true)
        const cleanup = registerRefreshCallback(doRefresh)
        const interval = setInterval(() => load(false), 10000)
        return () => { clearInterval(interval); cleanup() }
    }, [registerRefreshCallback])

    const networkKeys = useMemo(() => Object.keys(data?.networks || {}), [data])

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>Cluster Info</h1>
                    <p className={`${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Database clock and node status per network</p>
                </div>
                {refreshing && (
                    <div className={`flex items-center space-x-2 text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></span>
                        <span>Updating...</span>
                    </div>
                )}
            </div>

            {loading && (
                <div className="card p-6">Loading cluster info…</div>
            )}
            {error && (
                <div className="card p-6 border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300">{error}</div>
            )}

            {!loading && !error && data && networkKeys.map((netId) => {
                const info: ClusterInfo = data.networks[netId]
                const nodeIds = Object.keys(info.node_statuses)
                // Calculate basic stats
                const online = nodeIds.filter(id => info.node_statuses[id] === 'online').length
                const offline = nodeIds.filter(id => info.node_statuses[id] === 'offline').length

                return (
                    <div key={netId} className="card p-6 data-fade overflow-hidden">
                        <div className="flex items-center justify-between gap-3 flex-wrap">
                            <h3 className={`text-lg font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>Network: {netId}</h3>
                            <div className="flex gap-2 flex-nowrap overflow-x-auto md:flex-wrap md:overflow-visible">
                                <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${isDark ? 'bg-blue-900/40 text-blue-300' : 'bg-blue-100 text-blue-700'}`}>Total: {nodeIds.length}</span>
                                <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${isDark ? 'bg-green-900/40 text-green-300' : 'bg-green-100 text-green-700'}`}>Online: {online}</span>
                                <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${isDark ? 'bg-red-900/40 text-red-300' : 'bg-red-100 text-red-700'}`}>Offline: {offline}</span>
                            </div>
                        </div>

                        {/* Node statuses grid: responsive, scroll on small if needed */}
                        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                            {nodeIds.map((nodeId) => (
                                <div key={nodeId} className={`rounded-lg border p-3 flex items-center justify-between shadow-sm ${isDark ? 'border-gray-600 bg-gray-700' : 'border-gray-200 bg-gray-50'}`}>
                                    <div className="min-w-0 pr-3">
                                        <div className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>Node</div>
                                        <div className={`truncate font-mono text-xs md:text-sm ${isDark ? 'text-gray-100' : 'text-gray-900'}`} title={nodeId}>{nodeId}</div>
                                    </div>
                                    <span className={`text-xs px-2 py-1 rounded-full whitespace-nowrap ${badgeClass(info.node_statuses[nodeId], isDark)}`}>{info.node_statuses[nodeId]}</span>
                                </div>
                            ))}
                        </div>

                        {/* Clock cards: show node time (HH:MM:SS.mmm) and delta in cards */}
                        <div className="mt-6">
                            <h4 className={`text-md font-medium mb-2 ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>Clock</h4>
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                                {Object.entries(info.clock_table).map(([nodeId, entry]) => (
                                    <div
                                        key={nodeId}
                                        className={`rounded-lg border p-3 shadow-sm ${isDark ? 'border-gray-600 bg-gray-700' : 'border-gray-200 bg-gray-50'}`}
                                    >
                                        <div className="flex items-center justify-between gap-3">
                                            <div className="min-w-0">
                                                <div className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>Node</div>
                                                <div className={`truncate font-mono text-xs md:text-sm ${isDark ? 'text-gray-100' : 'text-gray-900'}`} title={nodeId}>{nodeId}</div>
                                            </div>
                                            <div className="text-right">
                                                <div className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>Delta (ms)</div>
                                                <div className={`font-mono ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{entry.delta_ms.toFixed(2)}</div>
                                            </div>
                                        </div>
                                        <div className="mt-3">
                                            <div className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>Node Time</div>
                                            <div className={`font-mono text-sm ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{formatTimeWithMs(entry.node_time)}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )
            })}
        </div>
    )
}
