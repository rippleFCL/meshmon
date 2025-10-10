import React from 'react'
import { useTheme } from '../../contexts/ThemeContext'
import { getStatusColor, getConnectionStatusColor } from '../shared/status'
import ConnectionList, { NodeAdj } from './ConnectionList'

type Agg = { average_rtt: number; online_connections: number; total_connections: number; status: 'online' | 'offline' | 'degraded' | 'unknown' }

interface Props {
    monitorId: string
    monitorStatus: 'online' | 'offline' | 'unknown'
    inboundInfo: Record<string, { status: 'online' | 'offline' | 'unknown'; rtt: number }>
    inboundAgg: Agg
    isExpanded: boolean
    onToggle: () => void
    useUnifiedLayout: boolean
}

const MonitorDetailCard: React.FC<Props> = ({ monitorId, monitorStatus, inboundInfo, inboundAgg, isExpanded, onToggle, useUnifiedLayout }) => {
    const { isDark } = useTheme()
    const avgRtt = inboundAgg.average_rtt || 0

    const renderMonitorContent = () => {
        if (useUnifiedLayout) {
            return (
                <div className={`border rounded-lg p-3 ${isDark ? 'border-gray-600' : 'border-gray-200'}`}>
                    <div className="flex items-center justify-between mb-3">
                        <h5 className={`font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>Monitor Connections</h5>
                        <div className="flex items-center space-x-4 text-xs">
                            <div className="flex items-center space-x-1">
                                <span className={`w-2 h-2 rounded-full bg-green-500`}></span>
                                <span className={`${isDark ? 'text-gray-400' : 'text-gray-600'}`}>→ Node can reach monitor</span>
                            </div>
                            <div className="flex items-center space-x-1">
                                <span className={`w-2 h-2 rounded-full bg-red-500`}></span>
                                <span className={`${isDark ? 'text-gray-400' : 'text-gray-600'}`}>✕ Cannot reach monitor</span>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2">
                        {Object.entries(inboundInfo).map(([targetNodeId, connection]) => {
                            const isOnline = connection.status === 'online'
                            const connectionType = isOnline ? '→' : '✕'
                            const connectionColor = isOnline
                                ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                                : 'border-red-500 bg-red-50 dark:bg-red-900/20'

                            return (
                                <div key={targetNodeId} className={`border-2 rounded p-1.5 ${connectionColor} ${isDark ? 'bg-gray-800' : 'bg-white'} shadow-sm`}>
                                    <div className="flex items-center justify-between mb-0.5">
                                        <h6 className={`text-sm font-semibold ${isDark ? 'text-gray-100' : 'text-gray-900'} truncate pr-1`}>
                                            {targetNodeId} {connectionType} {monitorId}
                                        </h6>
                                        <div className={`text-lg ${isDark ? 'text-gray-300' : 'text-gray-700'} flex-shrink-0`}>
                                            {connectionType}
                                        </div>
                                    </div>
                                    <div className="space-y-0">
                                        <div className={`text-xs ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                                            Status: <span className={`font-medium ${isOnline ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>{connection.status}</span>
                                        </div>
                                        <div className={`text-xs ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>
                                            RTT: <span className="font-mono font-medium">{connection.rtt > 0 ? `${connection.rtt.toFixed(1)}ms` : 'N/A'}</span>
                                        </div>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )
        }

        return (
            <ConnectionList
                title="Incoming Monitor Connections"
                connections={inboundInfo as NodeAdj}
                averageRtt={inboundAgg.average_rtt}
                onlineCount={inboundAgg.online_connections}
                totalCount={inboundAgg.total_connections}
                status={inboundAgg.status}
                description="Nodes that can reach this monitor"
            />
        )
    }

    return (
        <div className="card p-2">
            <div className={`flex items-center justify-between cursor-pointer py-1 px-2 rounded-lg transition-colors duration-200 ${isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50'}`} onClick={onToggle}>
                <div className="flex items-center space-x-3">
                    <span className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{isExpanded ? '▼' : '▶'}</span>
                    <h4 className={`text-base font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{monitorId}</h4>
                    <span className={`px-2 py-1 text-xs font-medium rounded ${isDark ? 'bg-purple-900/30 text-purple-400' : 'bg-purple-100 text-purple-700'}`}>
                        Monitor
                    </span>
                </div>

                <div className={`flex items-center gap-6 text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Status</div>
                        <div className={`px-2 py-0.5 text-xs font-medium rounded-full ${getStatusColor(monitorStatus)}`}>{monitorStatus}</div>
                    </div>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Avg Ping</div>
                        <div className="font-mono text-sm">{avgRtt.toFixed(1)}ms</div>
                    </div>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Monitored By</div>
                        <div className={`px-2 py-0.5 text-xs font-medium rounded-full ${getConnectionStatusColor(inboundAgg.online_connections, inboundAgg.total_connections)}`}>
                            {inboundAgg.online_connections}/{inboundAgg.total_connections}
                        </div>
                    </div>
                </div>
            </div>

            {isExpanded && <div className="mt-3">{renderMonitorContent()}</div>}
        </div>
    )
}

export default MonitorDetailCard
