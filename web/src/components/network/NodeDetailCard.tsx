import React from 'react'
import { useTheme } from '../../contexts/ThemeContext'
import { getConnectionStatusColor, getStatusColor } from '../shared/status'
import ConnectionList, { NodeAdj } from './ConnectionList'

type Agg = { average_rtt: number; online_connections: number; total_connections: number; status: 'online' | 'offline' | 'degraded' | 'unknown' }

interface Props {
    nodeId: string
    nodeStatus: 'online' | 'offline' | 'unknown'
    inboundInfo: NodeAdj
    outboundInfo: NodeAdj
    inboundAgg: Agg
    outboundAgg: Agg
    version: string
    isExpanded: boolean
    onToggle: () => void
    useUnifiedLayout: boolean
}

const NodeDetailCard: React.FC<Props> = ({ nodeId, nodeStatus, inboundInfo, outboundInfo, inboundAgg, outboundAgg, version, isExpanded, onToggle, useUnifiedLayout }) => {
    const { isDark } = useTheme()
    const avgInboundRtt = inboundAgg.average_rtt || 0
    const avgOutboundRtt = outboundAgg.average_rtt || 0
    const avgRtt = (avgInboundRtt + avgOutboundRtt) / 2

    const renderConnectionContent = () => {
        if (useUnifiedLayout) {
            return (
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
                            const allNodes = new Set([
                                ...Object.keys(inboundInfo),
                                ...Object.keys(outboundInfo)
                            ])

                            const connectionData = Array.from(allNodes).map(targetNodeId => {
                                const inbound = inboundInfo[targetNodeId]
                                const outbound = outboundInfo[targetNodeId]

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

                                return { targetNodeId, connectionType, connectionColor, rttText, sortOrder, isBidirectional, inbound, outbound }
                            })

                            const sortedConnections = connectionData.sort((a, b) => {
                                if (a.sortOrder !== b.sortOrder) return a.sortOrder - b.sortOrder
                                return a.targetNodeId.localeCompare(b.targetNodeId)
                            })

                            return sortedConnections.map(({ targetNodeId, connectionType, connectionColor, rttText, isBidirectional, inbound, outbound }) => (
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
                            ))
                        })()}
                    </div>
                </div>
            )
        }

        return (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <ConnectionList title="Incoming Connections" connections={inboundInfo} averageRtt={inboundAgg.average_rtt} onlineCount={inboundAgg.online_connections} totalCount={inboundAgg.total_connections} status={inboundAgg.status} />
                <ConnectionList title="Outgoing Connections" connections={outboundInfo} averageRtt={outboundAgg.average_rtt} onlineCount={outboundAgg.online_connections} totalCount={outboundAgg.total_connections} status={outboundAgg.status} />
            </div>
        )
    }

    return (
        <div className="card p-2">
            <div className={`flex items-center justify-between cursor-pointer py-1 px-2 rounded-lg transition-colors duration-200 ${isDark ? 'hover:bg-gray-700' : 'hover:bg-gray-50'}`} onClick={onToggle}>
                <div className="flex items-center space-x-3">
                    <span className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-700'}`}>{isExpanded ? '▼' : '▶'}</span>
                    <h4 className={`text-base font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{nodeId}</h4>
                </div>

                <div className={`flex items-center gap-6 text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Status</div>
                        <div className={`px-2 py-0.5 text-xs font-medium rounded-full ${getStatusColor(nodeStatus)}`}>{nodeStatus}</div>
                    </div>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Ping</div>
                        <div className="font-mono text-sm">{avgRtt.toFixed(1)}ms</div>
                    </div>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Receives</div>
                        <div className={`px-2 py-0.5 text-xs font-medium rounded-full ${getConnectionStatusColor(inboundAgg.online_connections, inboundAgg.total_connections)}`}>
                            {inboundAgg.online_connections}/{inboundAgg.total_connections}
                        </div>
                    </div>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Sends to</div>
                        <div className={`px-2 py-0.5 text-xs font-medium rounded-full ${getConnectionStatusColor(outboundAgg.online_connections, outboundAgg.total_connections)}`}>
                            {outboundAgg.online_connections}/{outboundAgg.total_connections}
                        </div>
                    </div>
                    <div className="text-center min-w-[4rem]">
                        <div className="font-medium">Version</div>
                        <div className={`text-xs px-1.5 py-0.5 rounded ${isDark ? 'bg-blue-900/30 text-blue-400' : 'bg-blue-100 text-blue-700'}`}>{version}</div>
                    </div>
                </div>
            </div>

            {isExpanded && <div className="mt-3">{renderConnectionContent()}</div>}
        </div>
    )
}

export default NodeDetailCard
