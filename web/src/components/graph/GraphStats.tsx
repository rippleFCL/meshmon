export default function GraphStats({ totalNodes, onlineNodes, connections, shownConnections }: { totalNodes: number, onlineNodes: number, connections: number, shownConnections: number }) {
    return (
        <div className="space-y-1 text-xs">
            <div className="font-medium text-gray-900 dark:text-gray-100">Connection Info</div>
            <div className="text-gray-600 dark:text-gray-400">Total Nodes: {totalNodes}</div>
            <div className="text-gray-600 dark:text-gray-400">Online Nodes: {onlineNodes}</div>
            <div className="text-gray-600 dark:text-gray-400">Connections: {connections}</div>
            <div className="text-gray-600 dark:text-gray-400">Shown Connections: {shownConnections}</div>
        </div>
    )
}
