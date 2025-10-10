import React from 'react'
import { useTheme } from '../../contexts/ThemeContext'
import { getStatusColor } from '../shared/status'

export type NodeLink = { status: 'online' | 'offline' | 'unknown'; rtt: number }
export type NodeAdj = Record<string, NodeLink>

interface Props {
    title: string
    connections: NodeAdj
    averageRtt: number
    onlineCount: number
    totalCount: number
    status: string
    description?: string
}

export const ConnectionList: React.FC<Props> = ({ title, connections, averageRtt, onlineCount, totalCount, status, description }) => {
    const { isDark } = useTheme()

    const getDescription = (title: string) => {
        if (description) return description
        if (title === 'Incoming Connections') return 'Nodes that can reach this node'
        return 'Nodes this node can reach'
    }

    return (
        <div className={`mt-2 border rounded-lg p-3 ${isDark ? 'border-gray-600' : 'border-gray-200'}`}>
            <div className="flex items-center justify-between mb-2">
                <div>
                    <h5 className={`font-medium ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{title}</h5>
                    <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{getDescription(title)}</p>
                </div>
                <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(status)}`}>{status}</span>
                    <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{onlineCount}/{totalCount} reachable</span>
                </div>
            </div>

            {totalCount > 0 && (
                <div className={`mb-2 text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                    Average response time: {averageRtt.toFixed(2)}ms
                </div>
            )}

            <div className="space-y-1">
                {Object.entries(connections).map(([targetNodeId, connection]) => (
                    <div key={targetNodeId} className={`flex items-center justify-between py-2 px-3 rounded ${isDark ? 'bg-gray-700' : 'bg-gray-50'}`}>
                        <span className={`font-medium text-sm ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>{targetNodeId}</span>
                        <div className="flex items-center space-x-2">
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(connection.status)}`}>{connection.status}</span>
                            <span className={`text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>{connection.rtt > 0 ? `${connection.rtt.toFixed(2)}ms` : 'N/A'}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}

export default ConnectionList
