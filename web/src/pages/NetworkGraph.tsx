import { useCallback, useMemo, useState, useEffect } from 'react'
import ReactFlow, {
    Node,
    Edge,
    addEdge,
    Connection,
    useNodesState,
    useEdgesState,
    Controls,
    MiniMap,
    Background,
    Panel,
    NodeTypes,
    Handle,
    Position,
    MarkerType,
    BackgroundVariant,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { meshmonApi } from '../api'
import { MultiNetworkAnalysis } from '../types'
import { useTheme } from '../contexts/ThemeContext'
import { useRefresh } from '../contexts/RefreshContext'
import { Wifi, WifiOff, Activity, Zap } from 'lucide-react'

// Custom node component for mesh nodes
const MeshNode = ({ data }: { data: any }) => {
    const { isDark } = useTheme()

    const isOnline = data.status === 'online'
    const statusColor = isOnline ? 'bg-green-500' : 'bg-red-500'
    const statusIcon = isOnline ? Wifi : WifiOff
    const StatusIcon = statusIcon

    // Calculate node importance based on connectivity
    const importance = Math.min(1, data.totalConnections / 15)
    const nodeSize = 140 + (importance * 40) // Scale from 140px to 180px based on connectivity

    // Apply opacity based on hover state
    const isHighlighted = data.isHighlighted
    const isDimmed = data.isDimmed
    const nodeOpacity = isDimmed ? 0.3 : isHighlighted ? 1 : 1
    const handleHover = data.onHover

    return (
        <>
            {/* Outbound connection handles (source) - positioned at outer corners to avoid crossovers */}
            <Handle
                type="source"
                position={Position.Top}
                id="top-out"
                style={{
                    background: '#3b82f6', // Blue for outbound
                    border: '2px solid',
                    borderColor: isOnline ? '#22c55e' : '#ef4444',
                    width: 10,
                    height: 10,
                    top: -5,
                    left: '15%', // Far left on top edge
                }}
            />
            <Handle
                type="source"
                position={Position.Right}
                id="right-out"
                style={{
                    background: '#3b82f6', // Blue for outbound
                    border: '2px solid',
                    borderColor: isOnline ? '#22c55e' : '#ef4444',
                    width: 10,
                    height: 10,
                    right: -5,
                    top: '15%', // High on right edge
                }}
            />
            <Handle
                type="source"
                position={Position.Bottom}
                id="bottom-out"
                style={{
                    background: '#3b82f6', // Blue for outbound
                    border: '2px solid',
                    borderColor: isOnline ? '#22c55e' : '#ef4444',
                    width: 10,
                    height: 10,
                    bottom: -5,
                    left: '85%', // Far right on bottom edge
                }}
            />
            <Handle
                type="source"
                position={Position.Left}
                id="left-out"
                style={{
                    background: '#3b82f6', // Blue for outbound
                    border: '2px solid',
                    borderColor: isOnline ? '#22c55e' : '#ef4444',
                    width: 10,
                    height: 10,
                    left: -5,
                    top: '85%', // Low on left edge
                }}
            />

            {/* Inbound connection handles (target) - positioned at inner corners to avoid crossovers */}
            <Handle
                type="target"
                position={Position.Top}
                id="top-in"
                style={{
                    background: '#f59e0b', // Orange for inbound
                    border: '2px solid',
                    borderColor: isOnline ? '#22c55e' : '#ef4444',
                    width: 10,
                    height: 10,
                    top: -5,
                    left: '85%', // Far right on top edge
                }}
            />
            <Handle
                type="target"
                position={Position.Right}
                id="right-in"
                style={{
                    background: '#f59e0b', // Orange for inbound
                    border: '2px solid',
                    borderColor: isOnline ? '#22c55e' : '#ef4444',
                    width: 10,
                    height: 10,
                    right: -5,
                    top: '85%', // Low on right edge
                }}
            />
            <Handle
                type="target"
                position={Position.Bottom}
                id="bottom-in"
                style={{
                    background: '#f59e0b', // Orange for inbound
                    border: '2px solid',
                    borderColor: isOnline ? '#22c55e' : '#ef4444',
                    width: 10,
                    height: 10,
                    bottom: -5,
                    left: '15%', // Far left on bottom edge
                }}
            />
            <Handle
                type="target"
                position={Position.Left}
                id="left-in"
                style={{
                    background: '#f59e0b', // Orange for inbound
                    border: '2px solid',
                    borderColor: isOnline ? '#22c55e' : '#ef4444',
                    width: 10,
                    height: 10,
                    left: -5,
                    top: '15%', // High on left edge
                }}
            />

            <div
                className={`
                    px-4 py-3 rounded-2xl border-2 shadow-lg backdrop-blur-sm
                    transition-all duration-300 hover:scale-105 hover:shadow-xl
                    ${isOnline
                        ? isDark
                            ? 'bg-gray-800/90 border-green-400 text-white shadow-green-400/20'
                            : 'bg-white/95 border-green-500 text-gray-900 shadow-green-500/20'
                        : isDark
                            ? 'bg-gray-800/70 border-red-400 text-gray-300 shadow-red-400/20'
                            : 'bg-white/85 border-red-500 text-gray-700 shadow-red-500/20'
                    }
                `}
                style={{
                    minWidth: `${nodeSize}px`,
                    maxWidth: `${nodeSize + 40}px`,
                    opacity: nodeOpacity,
                    transition: 'opacity 0.2s ease-in-out, transform 0.3s ease-in-out'
                }}
                onMouseEnter={() => handleHover && handleHover(data.label)}
                onMouseLeave={() => handleHover && handleHover(null)}
            >
                <div className="flex items-center justify-between mb-2">
                    <div className={`
                        w-4 h-4 rounded-full shadow-sm
                        ${statusColor}
                        ${isOnline ? 'animate-pulse' : ''}
                    `} />
                    <StatusIcon className={`
                        w-5 h-5
                        ${isOnline ? 'text-green-500' : 'text-red-500'}
                    `} />
                </div>

                <div className="text-sm font-bold truncate mb-1" title={data.label}>
                    {data.label}
                </div>

                <div className={`
                    text-xs font-medium mb-2
                    ${isOnline ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}
                `}>
                    {isOnline ? 'Online' : 'Offline'}
                </div>

                {data.avgRtt !== undefined && data.avgRtt > 0 && isOnline && (
                    <div className="text-xs opacity-80 mb-1">
                        Avg RTT: {data.avgRtt.toFixed(1)}ms
                    </div>
                )}

                <div className="flex justify-between text-xs opacity-70">
                    <span title="Inbound connections">↓{data.inboundCount}</span>
                    <span title="Outbound connections">↑{data.outboundCount}</span>
                </div>

                {importance > 0.3 && (
                    <div className="mt-1 px-2 py-1 rounded-full bg-blue-500/20 text-blue-600 dark:text-blue-400 text-xs text-center">
                        Hub Node
                    </div>
                )}
            </div>
        </>
    )
}

const nodeTypes: NodeTypes = {
    meshNode: MeshNode,
}

export default function NetworkGraph() {
    const { isDark } = useTheme()
    const { registerRefreshCallback } = useRefresh()
    const [selectedNetwork, setSelectedNetwork] = useState<string | null>(null)
    const [nodes, setNodes, onNodesChange] = useNodesState([])
    const [edges, setEdges, onEdgesChange] = useEdgesState([])
    const [networkData, setNetworkData] = useState<MultiNetworkAnalysis | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [hoveredNode, setHoveredNode] = useState<string | null>(null)

    // Function to handle node hover and update opacity
    const handleNodeHover = useCallback((hoveredNodeId: string | null) => {
        setHoveredNode(hoveredNodeId)
    }, [])

    // Update nodes and edges based on hover state without triggering viewport reset
    useEffect(() => {
        if (!hoveredNode) {
            // Reset all nodes and edges to normal state
            setNodes(currentNodes => {
                const updated = currentNodes.map(node => {
                    if (node.data.isHighlighted || node.data.isDimmed) {
                        return {
                            ...node,
                            data: {
                                ...node.data,
                                isHighlighted: false,
                                isDimmed: false
                            }
                        }
                    }
                    return node
                })
                return updated
            })
            setEdges(currentEdges => {
                const updated = currentEdges.map(edge => {
                    const originalOpacity = edge.animated ? 0.9 : 0.6
                    const needsUpdate = edge.style?.opacity !== originalOpacity ||
                        edge.label !== edge.data?.originalLabel

                    if (needsUpdate) {
                        return {
                            ...edge,
                            style: {
                                ...edge.style,
                                opacity: originalOpacity
                            },
                            label: edge.data?.originalLabel,
                            labelStyle: edge.data?.originalLabelStyle,
                            labelBgStyle: edge.data?.originalLabelBgStyle
                        }
                    }
                    return edge
                })
                return updated
            })
        } else {
            // Find connected nodes and edges
            const connectedNodeIds = new Set<string>([hoveredNode])
            const relevantEdgeIds = new Set<string>()

            // Find all edges connected to the hovered node
            edges.forEach(edge => {
                if (edge.source === hoveredNode || edge.target === hoveredNode) {
                    connectedNodeIds.add(edge.source)
                    connectedNodeIds.add(edge.target)
                    relevantEdgeIds.add(edge.id)
                }
            })

            // Update nodes with hover state only if changes are needed
            setNodes(currentNodes => {
                const updated = currentNodes.map(node => {
                    const shouldHighlight = node.id === hoveredNode
                    const shouldDim = !connectedNodeIds.has(node.id)

                    if (node.data.isHighlighted !== shouldHighlight || node.data.isDimmed !== shouldDim) {
                        return {
                            ...node,
                            data: {
                                ...node.data,
                                isHighlighted: shouldHighlight,
                                isDimmed: shouldDim
                            }
                        }
                    }
                    return node
                })
                return updated
            })

            // Update edges with hover state only if changes are needed
            setEdges(currentEdges => {
                const updated = currentEdges.map(edge => {
                    const isRelevant = relevantEdgeIds.has(edge.id)
                    const originalOpacity = edge.animated ? 0.9 : 0.6
                    const targetOpacity = isRelevant ? originalOpacity : 0

                    // Show labels only for relevant edges
                    const shouldShowLabel = isRelevant && edge.data?.originalLabel
                    const currentHasLabel = edge.label !== undefined

                    if (edge.style?.opacity !== targetOpacity || (shouldShowLabel !== currentHasLabel)) {
                        return {
                            ...edge,
                            style: {
                                ...edge.style,
                                opacity: targetOpacity
                            },
                            label: shouldShowLabel ? edge.data?.originalLabel : undefined,
                            labelStyle: shouldShowLabel ? edge.data?.originalLabelStyle : undefined,
                            labelBgStyle: shouldShowLabel ? edge.data?.originalLabelBgStyle : undefined
                        }
                    }
                    return edge
                })
                return updated
            })
        }
    }, [hoveredNode, edges, setNodes, setEdges])

    const fetchData = useCallback(async () => {
        try {
            setLoading(true)
            setError(null)
            const response = await meshmonApi.getViewData()
            setNetworkData(response.data)
        } catch (err) {
            setError('Failed to load network data')
            console.error('Error fetching network data:', err)
        } finally {
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchData()
        registerRefreshCallback(fetchData)
    }, [fetchData, registerRefreshCallback])

    const networks = useMemo(() => {
        if (!networkData?.networks) return []
        return Object.keys(networkData.networks).map(networkId => ({
            id: networkId,
            name: networkId,
            ...networkData.networks[networkId]
        }))
    }, [networkData])


    // Convert mesh data to nodes and edges
    const { processedNodes, processedEdges } = useMemo(() => {
        if (!networkData?.networks || !selectedNetwork) {
            return { processedNodes: [], processedEdges: [] }
        }

        const network = networkData.networks[selectedNetwork]
        if (!network) return { processedNodes: [], processedEdges: [] }

        const nodes: Node[] = []
        const edges: Edge[] = []
        const nodeIds = Object.keys(network.node_analyses)

        console.log('Network data for', selectedNetwork, ':', network)
        console.log('Node IDs:', nodeIds)

        // Create nodes with circular layout optimized for mesh networks
        const nodeMap = new Map<string, any>()

        // Sort nodes by connectivity for better visual organization
        const sortedNodes = nodeIds
            .map(nodeId => ({
                id: nodeId,
                analysis: network.node_analyses[nodeId],
                totalConnections: (network.node_analyses[nodeId].inbound_status?.total_connections || 0) +
                    (network.node_analyses[nodeId].outbound_status?.total_connections || 0)
            }))
            .sort((a, b) => b.totalConnections - a.totalConnections)

        sortedNodes.forEach((nodeInfo, index) => {
            const { id: nodeId, analysis: nodeAnalysis, totalConnections } = nodeInfo

            let x, y

            if (nodeIds.length === 1) {
                // Single node in center
                x = 0
                y = 0
            } else if (nodeIds.length === 2) {
                // Two nodes side by side with better spacing
                x = index === 0 ? -300 : 300 // Increased from 200
                y = 0
            } else if (nodeIds.length <= 12) {
                // Single circle for small to medium networks with better spacing
                const angle = (index / nodeIds.length) * 2 * Math.PI
                const radius = Math.max(350, nodeIds.length * 55) // Increased spacing significantly

                x = Math.cos(angle) * radius
                y = Math.sin(angle) * radius
            } else {
                // Concentric circles for larger networks with improved spacing
                const highConnectivityNodes = Math.min(6, Math.ceil(nodeIds.length * 0.3))

                if (index < highConnectivityNodes) {
                    // Inner circle for high-connectivity nodes
                    const innerAngle = (index / highConnectivityNodes) * 2 * Math.PI
                    const innerRadius = 280 // Increased from 180
                    x = Math.cos(innerAngle) * innerRadius
                    y = Math.sin(innerAngle) * innerRadius
                } else {
                    // Outer circle for remaining nodes
                    const outerIndex = index - highConnectivityNodes
                    const outerTotal = nodeIds.length - highConnectivityNodes
                    const outerAngle = (outerIndex / outerTotal) * 2 * Math.PI
                    const outerRadius = 580 // Increased from 380

                    x = Math.cos(outerAngle) * outerRadius
                    y = Math.sin(outerAngle) * outerRadius
                }
            }

            const nodeData = {
                id: nodeId,
                type: 'meshNode',
                position: { x, y },
                data: {
                    label: nodeId,
                    status: nodeAnalysis.node_status,
                    avgRtt: nodeAnalysis.inbound_status?.average_rtt || 0,
                    inboundCount: nodeAnalysis.inbound_status?.total_connections || 0,
                    outboundCount: nodeAnalysis.outbound_status?.total_connections || 0,
                    totalConnections,
                    version: nodeAnalysis.node_info?.version || 'unknown',
                    onHover: handleNodeHover,
                    isHighlighted: false,
                    isDimmed: false,
                },
            }

            nodes.push(nodeData)
            nodeMap.set(nodeId, nodeData)
        })

        // Helper function to determine the best connection handles based on node positions
        // Adjacent nodes connect on facing sides, distant nodes connect toward center
        const getOptimalHandles = (sourceX: number, sourceY: number, targetX: number, targetY: number, totalNodes: number) => {
            const dx = targetX - sourceX
            const dy = targetY - sourceY
            const distance = Math.sqrt(dx * dx + dy * dy)

            // Calculate network center (assuming nodes are arranged around origin)
            const networkCenterX = 0
            const networkCenterY = 0

            // Determine if nodes are adjacent based on distance
            // For small networks, nodes are more likely to be considered adjacent
            // For larger networks, we need a stricter threshold
            let adjacencyThreshold: number
            if (totalNodes <= 4) {
                adjacencyThreshold = 500 // More lenient for small networks
            } else if (totalNodes <= 8) {
                adjacencyThreshold = 400 // Increased from 300
            } else if (totalNodes <= 12) {
                adjacencyThreshold = 350 // Increased from 250
            } else {
                adjacencyThreshold = 300 // Increased from 200 - more connections will be face-to-face
            }

            const areAdjacent = distance < adjacencyThreshold

            if (areAdjacent) {
                // Adjacent nodes: connect on the sides that truly face each other
                // Using angle-based calculation for precise face-to-face connections
                // Calculate the angle between the two nodes to determine facing sides
                const angle = Math.atan2(dy, dx) // Angle from source to target
                const angleInDegrees = (angle * 180 / Math.PI + 360) % 360

                // Determine source handle based on direction to target
                let sourceHandle: string
                if (angleInDegrees >= 315 || angleInDegrees < 45) {
                    // Target is to the right
                    sourceHandle = 'right-out'
                } else if (angleInDegrees >= 45 && angleInDegrees < 135) {
                    // Target is below
                    sourceHandle = 'bottom-out'
                } else if (angleInDegrees >= 135 && angleInDegrees < 225) {
                    // Target is to the left
                    sourceHandle = 'left-out'
                } else {
                    // Target is above
                    sourceHandle = 'top-out'
                }

                // Determine target handle (opposite side from source perspective)
                let targetHandle: string
                if (angleInDegrees >= 315 || angleInDegrees < 45) {
                    // Source is to the left of target
                    targetHandle = 'left-in'
                } else if (angleInDegrees >= 45 && angleInDegrees < 135) {
                    // Source is above target
                    targetHandle = 'top-in'
                } else if (angleInDegrees >= 135 && angleInDegrees < 225) {
                    // Source is to the right of target
                    targetHandle = 'right-in'
                } else {
                    // Source is below target
                    targetHandle = 'bottom-in'
                }

                return { sourceHandle, targetHandle, isAdjacent: true }
            } else {
                // Distant nodes: connect toward the center for both source and target

                // Calculate direction from source to center
                const sourceToCenterX = networkCenterX - sourceX
                const sourceToCenterY = networkCenterY - sourceY

                // Calculate direction from target to center
                const targetToCenterX = networkCenterX - targetX
                const targetToCenterY = networkCenterY - targetY

                // Determine source handle (side facing toward center)
                let sourceHandle: string
                if (Math.abs(sourceToCenterX) > Math.abs(sourceToCenterY)) {
                    sourceHandle = sourceToCenterX > 0 ? 'right-out' : 'left-out'
                } else {
                    sourceHandle = sourceToCenterY > 0 ? 'bottom-out' : 'top-out'
                }

                // Determine target handle (side facing toward center)
                let targetHandle: string
                if (Math.abs(targetToCenterX) > Math.abs(targetToCenterY)) {
                    targetHandle = targetToCenterX > 0 ? 'right-in' : 'left-in'
                } else {
                    targetHandle = targetToCenterY > 0 ? 'bottom-in' : 'top-in'
                }

                return { sourceHandle, targetHandle, isAdjacent: false }
            }
        }

        // Create edges based exclusively on real outbound connections
        console.log('Creating authentic mesh connections for', nodeIds.length, 'nodes')
        console.log('Using intelligent handle selection: adjacent nodes connect face-to-face, distant nodes connect toward center')

        const createdConnections = new Set<string>()
        let realConnectionCount = 0
        let adjacentConnections = 0
        let centerConnections = 0

        // Debug: Track some example connections
        const debugConnections: Array<{ source: string, target: string, sourceHandle: string, targetHandle: string, isAdjacent: boolean }> = []

        // Create all real connections from outbound_info
        nodeIds.forEach(sourceNodeId => {
            const nodeAnalysis = network.node_analyses[sourceNodeId]
            const outboundInfo = nodeAnalysis.outbound_info || {}

            Object.keys(outboundInfo).forEach(targetNodeId => {
                if (nodeIds.includes(targetNodeId)) {
                    const connection = outboundInfo[targetNodeId]
                    const edgeId = `${sourceNodeId}-${targetNodeId}`

                    // Don't create duplicate connections
                    if (!createdConnections.has(edgeId)) {
                        const isOnline = connection.status === 'online'
                        const rtt = connection.rtt || 0

                        // Get node positions for handle calculation
                        const sourceNode = nodeMap.get(sourceNodeId)
                        const targetNode = nodeMap.get(targetNodeId)
                        const handleResult = getOptimalHandles(
                            sourceNode?.position.x || 0,
                            sourceNode?.position.y || 0,
                            targetNode?.position.x || 0,
                            targetNode?.position.y || 0,
                            nodeIds.length
                        )

                        // Track connection types for debugging
                        if (handleResult.isAdjacent) {
                            adjacentConnections++
                        } else {
                            centerConnections++
                        }

                        // Track some example connections for debugging
                        if (debugConnections.length < 5) {
                            debugConnections.push({
                                source: sourceNodeId,
                                target: targetNodeId,
                                sourceHandle: handleResult.sourceHandle,
                                targetHandle: handleResult.targetHandle,
                                isAdjacent: handleResult.isAdjacent
                            })
                        }

                        // Calculate edge strength based on RTT and status
                        const strength = isOnline ? Math.max(1, 5 - (rtt / 50)) : 0.5

                        // Different visual styles for adjacent vs center-oriented connections
                        const baseStrokeWidth = Math.max(1.5, Math.min(4, strength))
                        const strokeWidth = handleResult.isAdjacent ? baseStrokeWidth : baseStrokeWidth * 0.8 // Adjacent connections slightly thicker
                        const edgeOpacity = isOnline ? (handleResult.isAdjacent ? 0.9 : 0.7) : 0.6 // Adjacent connections more visible

                        edges.push({
                            id: edgeId,
                            source: sourceNodeId,
                            target: targetNodeId,
                            sourceHandle: handleResult.sourceHandle,
                            targetHandle: handleResult.targetHandle,
                            style: {
                                stroke: isOnline ? '#22c55e' : '#ef4444',
                                strokeWidth: strokeWidth,
                                strokeDasharray: isOnline ? '0' : '6,3',
                                opacity: edgeOpacity,
                            },
                            label: isOnline ? `${rtt.toFixed(0)}ms` : undefined,
                            labelStyle: isOnline ? {
                                fontSize: 11,
                                fontWeight: '600',
                                fill: '#16a34a',
                                background: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                                padding: '2px 6px',
                                borderRadius: '12px',
                                border: '1px solid #22c55e',
                            } : undefined,
                            labelBgStyle: isOnline ? {
                                fill: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                                fillOpacity: 0.9,
                            } : undefined,
                            data: {
                                originalLabel: isOnline ? `${rtt.toFixed(0)}ms` : undefined,
                                originalLabelStyle: isOnline ? {
                                    fontSize: 11,
                                    fontWeight: '600',
                                    fill: '#16a34a',
                                    background: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                                    padding: '2px 6px',
                                    borderRadius: '12px',
                                    border: '1px solid #22c55e',
                                } : undefined,
                                originalLabelBgStyle: isOnline ? {
                                    fill: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                                    fillOpacity: 0.9,
                                } : undefined,
                            },
                            animated: isOnline && rtt < 100,
                            type: 'bezier',
                            markerEnd: {
                                type: MarkerType.ArrowClosed,
                                color: isOnline ? '#22c55e' : '#ef4444',
                                width: 12,
                                height: 12,
                            },
                        })

                        createdConnections.add(edgeId)
                        realConnectionCount++
                    }
                }
            })
        })

        console.log(`Created ${realConnectionCount} authentic connections from outbound data`)
        console.log(`Connection types: ${adjacentConnections} adjacent (face-to-face), ${centerConnections} center-oriented`)
        console.log(`Sample face-to-face connections:`, debugConnections.filter(c => c.isAdjacent))

        console.log('Generated edges:', edges)
        return { processedNodes: nodes, processedEdges: edges }
    }, [networkData, selectedNetwork, isDark])

    // Update nodes and edges when processed data changes
    // Important: Set nodes first, then edges to avoid React Flow edge creation errors
    useEffect(() => {
        setNodes(processedNodes)
    }, [processedNodes, setNodes])

    useEffect(() => {
        // Only set edges after nodes are updated to avoid React Flow errors
        if (processedNodes.length > 0) {
            // Small delay to ensure React Flow has processed the nodes
            const timer = setTimeout(() => {
                setEdges(processedEdges)
            }, 100)
            return () => clearTimeout(timer)
        } else {
            setEdges([])
        }
    }, [processedEdges, processedNodes.length, setEdges])

    // Auto-select first network if none selected
    useEffect(() => {
        if (networks.length > 0 && !selectedNetwork) {
            setSelectedNetwork(networks[0].id)
        }
    }, [networks, selectedNetwork])

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges]
    )

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-center">
                    <Activity className="w-8 h-8 animate-spin mx-auto mb-4 text-primary-500" />
                    <p className="text-gray-600 dark:text-gray-400">Loading network data...</p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-center">
                    <WifiOff className="w-8 h-8 mx-auto mb-4 text-red-500" />
                    <p className="text-red-600 dark:text-red-400">Failed to load network data</p>
                </div>
            </div>
        )
    }

    if (networks.length === 0) {
        return (
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                        Network Graph
                    </h1>
                    <p className="text-gray-600 dark:text-gray-400 mt-1">
                        Interactive visualization of mesh network topology
                    </p>
                </div>
                <div className="flex items-center justify-center h-96">
                    <div className="text-center">
                        <Zap className="w-8 h-8 mx-auto mb-4 text-gray-400" />
                        <p className="text-gray-600 dark:text-gray-400">No networks found</p>
                        <p className="text-sm text-gray-500 dark:text-gray-500 mt-2">
                            Make sure your mesh monitoring system is running and has network data available.
                        </p>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                        Network Graph
                    </h1>
                    <p className="text-gray-600 dark:text-gray-400 mt-1">
                        Interactive visualization of mesh network topology
                    </p>
                </div>

                <div className="flex items-center space-x-4">
                    <select
                        value={selectedNetwork || ''}
                        onChange={(e) => setSelectedNetwork(e.target.value)}
                        className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    >
                        {networks.map(network => (
                            <option key={network.id} value={network.id}>
                                {network.name} ({network.online_nodes}/{network.total_nodes} online)
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            {selectedNetwork && (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                        <div className="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
                            <div className="text-sm text-gray-600 dark:text-gray-400">Total Nodes</div>
                            <div className="text-xl font-bold text-gray-900 dark:text-gray-100">
                                {networks.find(n => n.id === selectedNetwork)?.total_nodes || 0}
                            </div>
                        </div>
                        <div className="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
                            <div className="text-sm text-gray-600 dark:text-gray-400">Online Nodes</div>
                            <div className="text-xl font-bold text-green-600 dark:text-green-400">
                                {networks.find(n => n.id === selectedNetwork)?.online_nodes || 0}
                            </div>
                        </div>
                        <div className="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700">
                            <div className="text-sm text-gray-600 dark:text-gray-400">Connections</div>
                            <div className="text-xl font-bold text-blue-600 dark:text-blue-400">
                                {processedEdges.length}
                            </div>
                        </div>
                    </div>

                    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
                        <div className="p-3 border-b border-gray-200 dark:border-gray-700">
                            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">
                                Network Topology
                            </h3>
                            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                                Drag nodes to rearrange • Scroll to zoom • Click and drag to pan
                            </p>
                        </div>
                        <div className="h-[calc(100vh-24rem)] min-h-[300px] relative">
                            <ReactFlow
                                nodes={nodes}
                                edges={edges}
                                onNodesChange={onNodesChange}
                                onEdgesChange={onEdgesChange}
                                onConnect={onConnect}
                                nodeTypes={nodeTypes}
                                attributionPosition="bottom-left"
                                className={isDark ? 'dark' : ''}
                                defaultEdgeOptions={{
                                    type: 'bezier',
                                    animated: false,
                                    style: { strokeWidth: 2 }
                                }}
                                fitView
                                connectionLineStyle={{ strokeWidth: 2, stroke: '#10b981' }}
                                snapToGrid={false}
                                snapGrid={[15, 15]}
                                nodesDraggable={true}
                                nodesConnectable={false}
                                elementsSelectable={true}
                                selectNodesOnDrag={false}
                                panOnDrag={true}
                                zoomOnScroll={true}
                                zoomOnDoubleClick={true}
                                minZoom={0.1}
                                maxZoom={3.0}
                                zoomOnPinch={true}
                                nodeOrigin={[0.5, 0.5]}
                            >
                                <Background
                                    color={isDark ? '#374151' : '#e5e7eb'}
                                    gap={30}
                                    size={1}
                                    variant={BackgroundVariant.Dots}
                                />
                                <Controls
                                    className={`
                                        ${isDark ? 'bg-gray-800 border-gray-600' : 'bg-white border-gray-300'}
                                        shadow-lg rounded-lg
                                    `}
                                    showInteractive={false}
                                />
                                <MiniMap
                                    nodeColor={(node) => {
                                        const isOnline = node.data?.status === 'online'
                                        return isOnline ? '#22c55e' : '#ef4444'
                                    }}
                                    className={`
                                        ${isDark ? 'bg-gray-800 border-gray-600' : 'bg-white border-gray-300'}
                                        shadow-lg rounded-lg
                                    `}
                                    position="bottom-left"
                                    maskColor={isDark ? 'rgba(0, 0, 0, 0.7)' : 'rgba(255, 255, 255, 0.7)'}
                                />
                                <Panel position="top-right" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-3">
                                    <div className="space-y-3 text-xs">
                                        <div>
                                            <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-1.5">Network Legend</div>
                                            <div className="space-y-1.5">
                                                <div className="flex items-center space-x-2">
                                                    <div className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse"></div>
                                                    <span className="text-gray-600 dark:text-gray-400">Online Node</span>
                                                </div>
                                                <div className="flex items-center space-x-2">
                                                    <div className="w-2.5 h-2.5 bg-red-500 rounded-full"></div>
                                                    <span className="text-gray-600 dark:text-gray-400">Offline Node</span>
                                                </div>
                                                <div className="flex items-center space-x-2">
                                                    <div className="w-3 h-0.5 bg-green-500 rounded-full"></div>
                                                    <span className="text-gray-600 dark:text-gray-400">Active Link</span>
                                                </div>
                                                <div className="flex items-center space-x-2">
                                                    <div className="w-3 h-0.5 bg-red-500"></div>
                                                    <span className="text-gray-600 dark:text-gray-400">Failed Link</span>
                                                </div>
                                            </div>
                                        </div>
                                        <div>
                                            <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-1.5">Connection Handles</div>
                                            <div className="space-y-1.5">
                                                <div className="flex items-center space-x-2">
                                                    <div className="w-2.5 h-2.5 bg-blue-500 rounded-full"></div>
                                                    <span className="text-gray-600 dark:text-gray-400">Outbound Handle</span>
                                                </div>
                                                <div className="flex items-center space-x-2">
                                                    <div className="w-2.5 h-2.5 bg-amber-500 rounded-full"></div>
                                                    <span className="text-gray-600 dark:text-gray-400">Inbound Handle</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </Panel>
                                <Panel position="bottom-right" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-2">
                                    <div className="space-y-1 text-xs">
                                        <div className="font-medium text-gray-900 dark:text-gray-100">Debug Info</div>
                                        <div className="text-gray-600 dark:text-gray-400">
                                            Nodes: {processedNodes.length}
                                        </div>
                                        <div className="text-gray-600 dark:text-gray-400">
                                            Edges: {processedEdges.length}
                                        </div>
                                    </div>
                                </Panel>
                            </ReactFlow>
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
