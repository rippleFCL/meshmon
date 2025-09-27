import { useCallback, useMemo, useState, useEffect, useRef, memo } from 'react'
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
    MarkerType,
    BackgroundVariant,
    BaseEdge,
    EdgeLabelRenderer,
    getBezierPath,
    ReactFlowInstance,
    useReactFlow,
    Handle,
    Position,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { meshmonApi } from '../api'
import { MultiNetworkAnalysis } from '../types'
import { useTheme } from '../contexts/ThemeContext'
import { useRefresh } from '../contexts/RefreshContext'
import { Activity, Zap, WifiOff } from 'lucide-react'

// Toggle for verbose console logging in this module
const DEBUG = false
// Toggle for performance/graph mutation logs
const PERF_LOG = false
const logPerf = (...args: any[]) => {
    if (PERF_LOG) console.log('[Graph]', ...args)
}

// Estimate a node diameter from its label length to pre-allocate space/layout
const estimateDiameterFromLabel = (label?: string) => {
    const baseSize = 120
    const len = (label?.length ?? 0)
    const estWidth = Math.round(len * 8.5 + 40)
    return Math.max(baseSize, Math.min(220, estWidth))
}

// (Radial handle logic removed in favor of floating edges)

function FloatingBezierEdge({ id, source, target, markerStart, markerEnd, style, label, labelStyle }: any) {
    const rf = useReactFlow()
    const sourceNode = rf.getNode(source)
    const targetNode = rf.getNode(target)
    if (!sourceNode || !targetNode) return null

    const sPos = sourceNode.positionAbsolute || sourceNode.position
    const tPos = targetNode.positionAbsolute || targetNode.position
    const sW = sourceNode.width || 0
    const sH = sourceNode.height || 0
    const tW = targetNode.width || 0
    const tH = targetNode.height || 0

    // With nodeOrigin set to [0.5, 0.5], positionAbsolute is already the node center
    const sCenter = { x: (sPos.x || 0), y: (sPos.y || 0) }
    const tCenter = { x: (tPos.x || 0), y: (tPos.y || 0) }

    const rsRaw = (sourceNode.data && sourceNode.data.nodeRadius) ? sourceNode.data.nodeRadius : Math.max(20, Math.min(sW, sH) / 2)
    const rtRaw = (targetNode.data && targetNode.data.nodeRadius) ? targetNode.data.nodeRadius : Math.max(20, Math.min(tW, tH) / 2)
    // Account for border/antialiasing and marker size so the arrow tip lands on the circle border
    const strokeW = (style && (style as any).strokeWidth) ? Number((style as any).strokeWidth) : 2
    // Use no additional marker offset so the path endpoint is the border contact
    const markerOffset = 0
    const radiusInset = 2
    const rs = Math.max(0, rsRaw - radiusInset - strokeW * 0.5)
    const rt = Math.max(0, rtRaw - radiusInset - strokeW * 0.5)

    const dx = tCenter.x - sCenter.x
    const dy = tCenter.y - sCenter.y
    const len = Math.max(1, Math.hypot(dx, dy))
    const ux = dx / len
    const uy = dy / len

    const sourceX = sCenter.x + ux * rs
    const sourceY = sCenter.y + uy * rs
    // Pull the target point slightly inward to compensate for the arrowhead length
    const targetX = tCenter.x - ux * (rt + markerOffset)
    const targetY = tCenter.y - uy * (rt + markerOffset)

    // Choose positions based on dominant axis for nicer curvature
    const horizontal = Math.abs(dx) >= Math.abs(dy)
    const sourcePosition = horizontal
        ? (dx >= 0 ? 'right' : 'left')
        : (dy >= 0 ? 'bottom' : 'top')
    const targetPosition = horizontal
        ? (dx >= 0 ? 'left' : 'right')
        : (dy >= 0 ? 'top' : 'bottom')

    const [edgePath, labelX, labelY] = getBezierPath({
        sourceX,
        sourceY,
        targetX,
        targetY,
        sourcePosition: sourcePosition as any,
        targetPosition: targetPosition as any,
    })

    return (
        <>
            <BaseEdge id={id} path={edgePath} style={style} markerStart={markerStart} markerEnd={markerEnd} />
            {label && (
                <EdgeLabelRenderer>
                    <div
                        style={{
                            position: 'absolute',
                            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
                            pointerEvents: 'all',
                            ...(labelStyle || {}),
                        }}
                        className="nodrag nopan"
                    >
                        {label}
                    </div>
                </EdgeLabelRenderer>
            )}
        </>
    )
}

// Custom node component for mesh nodes
const MeshNode = memo(({ data }: { data: any }) => {
    const { isDark } = useTheme()

    const isOnline = data.status === 'online'
    // keep a simple status dot to reduce DOM; no icon to minimize SVG cost

    // Dynamic node size based on label length (fits bigger content)
    const baseSize = 120
    const labelLen = (data.label?.length ?? 0)
    // Approximate text width at text-sm bold ~8.5px per char + padding
    const estWidth = Math.round(labelLen * 8.5 + 40)
    const nodeSize = Math.max(baseSize, Math.min(220, estWidth))
    // Apply opacity based on hover state
    const isHighlighted = data.isHighlighted
    const isDimmed = data.isDimmed
    // effects removed for performance
    const nodeOpacity = isDimmed ? 0.1 : isHighlighted ? 1 : 1
    const handleHover = data.onHover
    DEBUG && console.log(`Node ${data.label} - Online: ${isOnline}, Inbound: ${data.inboundCount}, Outbound: ${data.outboundCount}`)
    return (
        <>
            <div
                className={`
                    relative flex flex-col items-center justify-center rounded-full border-2 shadow-none overflow-hidden
                    ${isOnline
                        ? (isDark ? 'bg-green-900/90 border-green-400 text-white' : 'bg-green-600 border-green-500 text-white')
                        : (isDark ? 'bg-red-900/90 border-red-400 text-white' : 'bg-red-600 border-red-500 text-white')
                    }
                `}
                style={{
                    width: `${nodeSize}px`,
                    height: `${nodeSize}px`,
                    opacity: nodeOpacity,
                    willChange: 'transform, opacity'
                }}
                onMouseEnter={() => handleHover && handleHover(data.nodeId || data.label)}
                onMouseLeave={() => handleHover && handleHover(null)}
            >

                <div className="text-sm font-bold truncate" title={data.label}>
                    {data.label}
                </div>


                <div className="text-xs opacity-80 mt-0.5">
                    Avg RTT: {Number.isFinite(data.avgRtt) ? `${(data.avgRtt as number).toFixed(1)}ms` : '—'}
                </div>

                <div className="flex items-center justify-center gap-4 text-xs opacity-80 mt-1">
                    <span title="Online/Total inbound connections">↓{data.inboundOnlineCount}/{data.inboundCount}</span>
                    <span title="Outbound connections">↑{data.outboundCount}</span>
                </div>

                {/* Minimal hidden handles to satisfy React Flow edge validation (inside node) */}
                <Handle type="source" id="s" position={Position.Right} isConnectable={false} style={{ width: 6, height: 6, opacity: 0, pointerEvents: 'none' }} />
                <Handle type="target" id="t" position={Position.Left} isConnectable={false} style={{ width: 6, height: 6, opacity: 0, pointerEvents: 'none' }} />
            </div>
        </>
    )
}, (prev, next) => {
    const a = prev.data, b = next.data
    return (
        a.isHighlighted === b.isHighlighted &&
        a.isDimmed === b.isDimmed &&
        a.status === b.status &&
        a.label === b.label &&
        a.avgRtt === b.avgRtt &&
        a.inboundOnlineCount === b.inboundOnlineCount &&
        a.inboundCount === b.inboundCount &&
        a.outboundCount === b.outboundCount
    )
})

// Custom node component for monitors
const MonitorNode = memo(({ data }: { data: any }) => {
    const { isDark } = useTheme()

    const isOnline = data.status === 'online'

    // Dynamic node size based on label length (fits bigger content)
    const nodeSize = estimateDiameterFromLabel(data.label)
    const isHighlighted = data.isHighlighted
    const isDimmed = data.isDimmed
    // effects removed for performance
    const nodeOpacity = isDimmed ? 0.1 : isHighlighted ? 1 : 1
    const handleHover = data.onHover

    return (
        <>
            <div
                className={`
                    relative flex flex-col items-center justify-center rounded-full border-2 shadow-none overflow-hidden
                    ${isOnline
                        ? (isDark ? 'bg-purple-900/90 border-purple-400 text-white' : 'bg-purple-600 border-purple-500 text-white')
                        : (isDark ? 'bg-red-900/90 border-red-400 text-white' : 'bg-red-600 border-red-500 text-white')
                    }
                `}
                style={{
                    width: `${nodeSize}px`,
                    height: `${nodeSize}px`,
                    opacity: nodeOpacity,
                    willChange: 'transform, opacity'
                }}
                onMouseEnter={() => handleHover && handleHover(data.nodeId || data.label)}
                onMouseLeave={() => handleHover && handleHover(null)}
            >
                <div className="text-sm font-bold truncate" title={data.label}>
                    {data.label}
                </div>
                <div className="text-xs opacity-80 mt-0.5">
                    Avg RTT: {Number.isFinite(data.avgRtt) ? `${(data.avgRtt as number).toFixed(1)}ms` : '—'}
                </div>

                <div className="flex justify-center text-xs opacity-80 mt-1">
                    <span title="Nodes monitoring this monitor">←{data.inboundOnlineCount}/{data.inboundCount}</span>
                </div>
                {/* Minimal hidden handles to satisfy React Flow edge validation (inside node) */}
                <Handle type="source" id="s" position={Position.Right} isConnectable={false} style={{ width: 6, height: 6, opacity: 0, pointerEvents: 'none' }} />
                <Handle type="target" id="t" position={Position.Left} isConnectable={false} style={{ width: 6, height: 6, opacity: 0, pointerEvents: 'none' }} />
            </div>
        </>
    )
}, (prev, next) => {
    const a = prev.data, b = next.data
    return (
        a.isHighlighted === b.isHighlighted &&
        a.isDimmed === b.isDimmed &&
        a.status === b.status &&
        a.label === b.label &&
        a.avgRtt === b.avgRtt &&
        a.inboundOnlineCount === b.inboundOnlineCount &&
        a.inboundCount === b.inboundCount
    )
})

const nodeTypes: NodeTypes = {
    meshNode: MeshNode,
    monitorNode: MonitorNode,
}
const edgeTypes = { floating: FloatingBezierEdge }

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
    const [isDragging, setIsDragging] = useState<boolean>(false)
    const [isPanning, setIsPanning] = useState<boolean>(false)
    const [layoutMode, setLayoutMode] = useState<'elk' | 'concentric' | 'dense' | 'pretty'>(() => 'pretty')
    const [hideOnlineByDefault, setHideOnlineByDefault] = useState<boolean>(true)
    // Animation policy for edges
    const [animationMode, setAnimationMode] = useState<'never' | 'hover' | 'always'>(() => 'hover')
    const [zoom, setZoom] = useState<number>(1)
    const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null)
    const reactFlowRef = useRef<ReactFlowInstance | null>(null)
    const focusingRef = useRef<boolean>(false)

    // Function to handle node hover and update opacity
    // Throttle hover updates to animation frames to avoid excessive re-renders
    const hoverRaf = useRef<number | null>(null)
    const pendingHover = useRef<string | null>(null)
    const handleNodeHover = useCallback((hoveredNodeId: string | null) => {
        pendingHover.current = hoveredNodeId
        if (hoverRaf.current !== null) return
        hoverRaf.current = requestAnimationFrame(() => {
            hoverRaf.current = null
            setHoveredNode(pendingHover.current)
        })
    }, [])

    // (Moved hover effect below processed graph data and adjacency maps)

    const fetchData = useCallback(async () => {
        try {
            logPerf('fetchData:start')
            setLoading(true)
            setError(null)
            const response = await meshmonApi.getViewData()
            setNetworkData(response.data)
        } catch (err) {
            setError('Failed to load network data')
            console.error('Error fetching network data:', err)
        } finally {
            logPerf('fetchData:end')
            setLoading(false)
        }
    }, [])

    useEffect(() => {
        fetchData()
        registerRefreshCallback(fetchData)
        // Load user settings
        try {
            const savedLayout = localStorage.getItem('meshmon.layoutMode')
            if (savedLayout === 'elk' || savedLayout === 'concentric' || savedLayout === 'dense' || savedLayout === 'pretty') {
                setLayoutMode(savedLayout)
            }
            const savedHide = localStorage.getItem('meshmon.hideOnlineByDefault')
            if (savedHide !== null) setHideOnlineByDefault(savedHide === 'true')
            const savedAnim = localStorage.getItem('meshmon.animationMode')
            if (savedAnim === 'never' || savedAnim === 'hover' || savedAnim === 'always') setAnimationMode(savedAnim)
        } catch { }
    }, [fetchData, registerRefreshCallback])

    // Persist user settings
    useEffect(() => {
        try {
            localStorage.setItem('meshmon.layoutMode', layoutMode)
            localStorage.setItem('meshmon.hideOnlineByDefault', String(hideOnlineByDefault))
            localStorage.setItem('meshmon.animationMode', animationMode)
        } catch { }
    }, [layoutMode, hideOnlineByDefault, animationMode])

    const networks = useMemo(() => {
        if (!networkData?.networks) return []
        return Object.keys(networkData.networks).map(networkId => ({
            id: networkId,
            name: networkId,
            ...networkData.networks[networkId]
        }))
    }, [networkData])

    // Initialize selected network from saved setting or first available
    useEffect(() => {
        if (!selectedNetwork && networks.length > 0) {
            let target = networks[0].id
            try {
                const savedNet = localStorage.getItem('meshmon.selectedNetwork')
                if (savedNet && networks.some(n => n.id === savedNet)) target = savedNet
            } catch { }
            setSelectedNetwork(target)
        }
    }, [networks, selectedNetwork])


    // Convert mesh data to nodes and edges
    const { processedNodes, processedEdges } = useMemo(() => {
        const t0 = performance.now()
        logPerf('processGraph:start')
        if (!networkData?.networks || !selectedNetwork) {
            logPerf('processGraph:empty')
            return { processedNodes: [], processedEdges: [] }
        }

        const network = networkData.networks[selectedNetwork]
        if (!network) return { processedNodes: [], processedEdges: [] }

        const nodes: Node[] = []
        const edges: Edge[] = []
        const nodeIds = Object.keys(network.node_analyses)
        const monitorIds = Object.keys(network.monitor_analyses || {})

        DEBUG && console.log('Network data for', selectedNetwork, ':', network)
        DEBUG && console.log('Node IDs:', nodeIds)
        DEBUG && console.log('Monitor IDs:', monitorIds)

        // Create nodes with circular layout optimized for mesh networks
        const nodeMap = new Map<string, any>()

        // Sort nodes by connectivity for better visual organization
        const sortedNodes = nodeIds
            .map(nodeId => ({
                id: nodeId,
                type: 'node',
                analysis: network.node_analyses[nodeId],
                totalConnections: (network.node_analyses[nodeId].inbound_status?.total_connections || 0) +
                    (network.node_analyses[nodeId].outbound_status?.total_connections || 0)
            }))
            .sort((a, b) => b.totalConnections - a.totalConnections)

        // Add monitors to the entity list
        const sortedMonitors = monitorIds.map(monitorId => ({
            id: monitorId,
            type: 'monitor',
            analysis: network.monitor_analyses![monitorId],
            totalConnections: network.monitor_analyses![monitorId].inbound_status?.total_connections || 0
        }))

        // Precompute entity counts
        const totalEntities = sortedNodes.length + sortedMonitors.length

        // Estimate diameters to inform spacing for dynamic-sized nodes
        const estNodeDiameters = sortedNodes.map(n => estimateDiameterFromLabel(n.id))
        const estMonDiameters = sortedMonitors.map(m => estimateDiameterFromLabel(m.id))
        const maxNodeDiam = estNodeDiameters.length ? Math.max(...estNodeDiameters) : 120
        const maxMonDiam = estMonDiameters.length ? Math.max(...estMonDiameters) : 120

        // Positioning by mode
        // - elk (Stacked): positions computed later by ELK, we still seed with a reasonable placement
        // - concentric: place nodes on inner ring and monitors on outer ring with coupled radii
        // - dense: compact grid centered on origin
        // - pretty: phyllotaxis (golden-angle) spiral for a pleasing arrangement
        if (layoutMode === 'concentric' || layoutMode === 'elk') {
            const nodeCount = sortedNodes.length
            const monitorCount = sortedMonitors.length
            // Spacing targets
            const NODE_SIZE = maxNodeDiam // px (mesh nodes)
            const MON_SIZE = maxMonDiam // px (monitor nodes)
            const CHORD_MARGIN = 24 // extra space between adjacent nodes on a ring
            const SEP_MARGIN = 80 // separation between rings
            // Arc-length targets scale with size so larger nodes get more space
            const nodeGap = NODE_SIZE + 60
            const monGap = MON_SIZE + 90

            // Minimal radii per ring based on chord and arc spacing
            const innerRChordMin = nodeCount > 1
                ? (NODE_SIZE + CHORD_MARGIN) / (2 * Math.sin(Math.PI / nodeCount))
                : 220
            const innerRArcMin = nodeCount > 0 ? (nodeCount * nodeGap) / (2 * Math.PI) : 220
            const innerMin = nodeCount > 0 ? Math.max(220, innerRChordMin, innerRArcMin) : 220

            const outerRChordMin = monitorCount > 1
                ? (MON_SIZE + CHORD_MARGIN) / (2 * Math.sin(Math.PI / monitorCount))
                : innerMin + 1 // placeholder; will be coupled below
            const outerRArcMin = monitorCount > 0 ? (monitorCount * monGap) / (2 * Math.PI) : innerMin + 1
            const outerMin = monitorCount > 0 ? Math.max(outerRChordMin, outerRArcMin) : innerMin + 1

            // Desired fixed separation between rings (kept small to bring them closer)
            const sep = (NODE_SIZE / 2) + (MON_SIZE / 2) + SEP_MARGIN

            // Couple the radii: if one ring grows, the other grows to maintain sep
            // Choose center radius C so that C >= innerMin and C + sep >= outerMin
            let C = Math.max(innerMin, outerMin - sep)
            const innerRadius = C
            const outerRadius = monitorCount > 0 ? C + sep : C + sep

            sortedNodes.forEach((entityInfo, index) => {
                const { id: entityId, analysis: entityAnalysis, totalConnections } = entityInfo
                const angle = (index / Math.max(1, nodeCount)) * 2 * Math.PI
                const x = Math.cos(angle) * innerRadius
                const y = Math.sin(angle) * innerRadius
                const nodeAnalysis = entityAnalysis as any
                const nodeData = {
                    id: entityId,
                    type: 'meshNode',
                    position: { x, y },
                    data: {
                        label: entityId,
                        status: nodeAnalysis.node_status,
                        avgRtt: nodeAnalysis.inbound_status?.average_rtt || 0,
                        inboundCount: nodeAnalysis.inbound_status?.total_connections || 0,
                        inboundOnlineCount: nodeAnalysis.inbound_status?.online_connections || 0,
                        outboundCount: nodeAnalysis.outbound_status?.total_connections || 0,
                        totalConnections,
                        version: nodeAnalysis.node_info?.version || 'unknown',
                        onHover: handleNodeHover,
                        isHighlighted: false,
                        isDimmed: false,
                        isPanning,

                    },
                }
                nodes.push(nodeData)
                nodeMap.set(entityId, nodeData)
            })

            sortedMonitors.forEach((entityInfo, index) => {
                const { id: entityId, analysis: entityAnalysis, totalConnections } = entityInfo
                const angle = (index / Math.max(1, monitorCount)) * 2 * Math.PI
                const x = Math.cos(angle) * outerRadius
                const y = Math.sin(angle) * outerRadius
                const monitorAnalysis = entityAnalysis as any
                const monitorData = {
                    id: entityId,
                    type: 'monitorNode',
                    position: { x, y },
                    data: {
                        label: entityId,
                        status: monitorAnalysis.monitor_status,
                        avgRtt: monitorAnalysis.inbound_status?.average_rtt || 0,
                        inboundCount: monitorAnalysis.inbound_status?.total_connections || 0,
                        inboundOnlineCount: monitorAnalysis.inbound_status?.online_connections || 0,
                        totalConnections,
                        onHover: handleNodeHover,
                        isHighlighted: false,
                        isDimmed: false,
                        isPanning,

                    },
                }
                nodes.push(monitorData)
                nodeMap.set(entityId, monitorData)
            })
        } else if (layoutMode === 'dense') {
            // Compact grid centered at origin: nodes first, then monitors
            const MAX_DIAM = Math.max(maxNodeDiam, maxMonDiam)
            // Tripled margin for denser grid spacing
            const CELL = MAX_DIAM + 72
            const allEntities = [...sortedNodes, ...sortedMonitors]
            const total = allEntities.length
            const cols = Math.max(1, Math.ceil(Math.sqrt(total)))
            const rows = Math.max(1, Math.ceil(total / cols))
            const gridW = cols * CELL
            const gridH = rows * CELL
            allEntities.forEach((entityInfo, index) => {
                const { id: entityId, type: entityType, analysis: entityAnalysis, totalConnections } = entityInfo as any
                const r = Math.floor(index / cols)
                const c = index % cols
                const x = (c + 0.5) * CELL - gridW / 2
                const y = (r + 0.5) * CELL - gridH / 2
                if (entityType === 'node') {
                    const nodeAnalysis = entityAnalysis
                    const nodeData = {
                        id: entityId,
                        type: 'meshNode',
                        position: { x, y },
                        data: {
                            label: entityId,
                            status: nodeAnalysis.node_status,
                            avgRtt: nodeAnalysis.inbound_status?.average_rtt || 0,
                            inboundCount: nodeAnalysis.inbound_status?.total_connections || 0,
                            inboundOnlineCount: nodeAnalysis.inbound_status?.online_connections || 0,
                            outboundCount: nodeAnalysis.outbound_status?.total_connections || 0,
                            totalConnections,
                            version: nodeAnalysis.node_info?.version || 'unknown',
                            onHover: handleNodeHover,
                            isHighlighted: false,
                            isDimmed: false,
                            isPanning,

                        },
                    }
                    nodes.push(nodeData)
                    nodeMap.set(entityId, nodeData)
                } else {
                    const monitorAnalysis = entityAnalysis
                    const monitorData = {
                        id: entityId,
                        type: 'monitorNode',
                        position: { x, y },
                        data: {
                            label: entityId,
                            status: monitorAnalysis.monitor_status,
                            avgRtt: monitorAnalysis.inbound_status?.average_rtt || 0,
                            inboundCount: monitorAnalysis.inbound_status?.total_connections || 0,
                            inboundOnlineCount: monitorAnalysis.inbound_status?.online_connections || 0,
                            totalConnections,
                            onHover: handleNodeHover,
                            isHighlighted: false,
                            isDimmed: false,
                            isPanning,

                        },
                    }
                    nodes.push(monitorData)
                    nodeMap.set(entityId, monitorData)
                }
            })
        } else if (layoutMode === 'pretty') {
            // Improved phyllotaxis (golden-angle) spiral with collision avoidance
            const golden = Math.PI * (3 - Math.sqrt(5)) // ~2.39996 rad
            const NODE_RADIUS = Math.max(60, Math.round(maxNodeDiam / 2))
            const MON_RADIUS = Math.max(60, Math.round(maxMonDiam / 2))
            // Tripled margin for wider spacing between entities
            const MARGIN = 48
            const NODE_DIAM = NODE_RADIUS * 2
            const MON_DIAM = MON_RADIUS * 2
            // Extra separation between different types to avoid tight boundaries
            const TYPE_SEP = Math.max(72, Math.round((NODE_RADIUS + MON_RADIUS) * 0.75))

            // Scale parameters derived from desired area per point: pi*c^2 ≈ s^2 => c ≈ s/√pi
            const cNode = (NODE_DIAM + MARGIN) / Math.sqrt(Math.PI)
            const cMon = (MON_DIAM + MARGIN) / Math.sqrt(Math.PI)

            type Placed = { x: number, y: number, r: number, type: 'node' | 'monitor' }
            const placed: Placed[] = []

            const placeEntity = (
                id: string,
                entityType: 'node' | 'monitor',
                analysis: any,
                totalConnections: number,
                index: number,
                angleOffset: number,
            ) => {
                const selfR = entityType === 'node' ? NODE_RADIUS : MON_RADIUS
                const c = entityType === 'node' ? cNode : cMon
                let angle = angleOffset + index * golden
                // Start monitors slightly farther out to create a soft band separation
                let r = c * Math.sqrt(index + 1) + (entityType === 'monitor' ? TYPE_SEP : 0)

                const maxIter = 30
                for (let iter = 0; iter < maxIter; iter++) {
                    const cx = Math.cos(angle) * r
                    const cy = Math.sin(angle) * r
                    let ok = true
                    for (const p of placed) {
                        const dx = cx - p.x
                        const dy = cy - p.y
                        const dist = Math.hypot(dx, dy)
                        const crossTypeMargin = (p.type !== entityType) ? TYPE_SEP : 0
                        if (dist < p.r + selfR + MARGIN + crossTypeMargin) {
                            ok = false
                            break
                        }
                    }
                    if (ok) {
                        placed.push({ x: cx, y: cy, r: selfR, type: entityType })
                        const dataCommon = {
                            label: id,
                            avgRtt: analysis.inbound_status?.average_rtt || 0,
                            inboundCount: analysis.inbound_status?.total_connections || 0,
                            inboundOnlineCount: analysis.inbound_status?.online_connections || 0,
                            totalConnections,
                            onHover: handleNodeHover,
                            isHighlighted: false,
                            isDimmed: false,
                        }
                        if (entityType === 'node') {
                            const nodeData = {
                                id,
                                type: 'meshNode' as const,
                                position: { x: cx, y: cy },
                                data: {
                                    ...dataCommon,
                                    status: analysis.node_status,
                                    outboundCount: analysis.outbound_status?.total_connections || 0,
                                    version: analysis.node_info?.version || 'unknown',
                                },
                            }
                            nodes.push(nodeData)
                            nodeMap.set(id, nodeData)
                        } else {
                            const monitorData = {
                                id,
                                type: 'monitorNode' as const,
                                position: { x: cx, y: cy },
                                data: {
                                    ...dataCommon,
                                    status: analysis.monitor_status,
                                },
                            }
                            nodes.push(monitorData)
                            nodeMap.set(id, monitorData)
                        }
                        return
                    }
                    // If collision, expand radius slightly and nudge angle a bit
                    // Slightly larger step when resolving collisions to reflect bigger margins
                    r += (selfR + MARGIN) * 0.9
                    angle += 0.03
                }
                // Fallback: push far out to avoid blocking
                const cx = Math.cos(angle) * (r + 200)
                const cy = Math.sin(angle) * (r + 200)
                placed.push({ x: cx, y: cy, r: selfR, type: entityType })
                if (entityType === 'node') {
                    const nodeData = {
                        id,
                        type: 'meshNode' as const,
                        position: { x: cx, y: cy },
                        data: {
                            label: id,
                            status: analysis.node_status,
                            avgRtt: analysis.inbound_status?.average_rtt || 0,
                            inboundCount: analysis.inbound_status?.total_connections || 0,
                            inboundOnlineCount: analysis.inbound_status?.online_connections || 0,
                            outboundCount: analysis.outbound_status?.total_connections || 0,
                            totalConnections,
                            version: analysis.node_info?.version || 'unknown',
                            onHover: handleNodeHover,
                            isHighlighted: false,
                            isDimmed: false,
                            isPanning,

                        },
                    }
                    nodes.push(nodeData)
                    nodeMap.set(id, nodeData)
                } else {
                    const monitorData = {
                        id,
                        type: 'monitorNode' as const,
                        position: { x: cx, y: cy },
                        data: {
                            label: id,
                            status: analysis.monitor_status,
                            avgRtt: analysis.inbound_status?.average_rtt || 0,
                            inboundCount: analysis.inbound_status?.total_connections || 0,
                            inboundOnlineCount: analysis.inbound_status?.online_connections || 0,
                            totalConnections,
                            onHover: handleNodeHover,
                            isHighlighted: false,
                            isDimmed: false,
                            isPanning,

                        },
                    }
                    nodes.push(monitorData)
                    nodeMap.set(id, monitorData)
                }
            }

            // Place nodes and monitors on two interleaved spirals for visual balance
            sortedNodes.forEach((n, i) => placeEntity(n.id, 'node', n.analysis as any, n.totalConnections, i, 0))
            sortedMonitors.forEach((m, i) => placeEntity(m.id, 'monitor', m.analysis as any, m.totalConnections, i, golden / 2))
        }

        // Simple adjacency check by straight-line distance (for styling)
        const isAdjacentByDistance = (sourceX: number, sourceY: number, targetX: number, targetY: number) => {
            const dx = targetX - sourceX
            const dy = targetY - sourceY
            const distance = Math.sqrt(dx * dx + dy * dy)
            const adjacencyThreshold = 350
            return distance < adjacencyThreshold
        }

        // Create edges based exclusively on real outbound connections
        DEBUG && console.log('Creating authentic mesh connections for', totalEntities, 'entities (', nodeIds.length, 'nodes +', monitorIds.length, 'monitors)')
        DEBUG && console.log('Using intelligent handle selection: adjacent entities connect face-to-face, distant entities connect toward center')

        // Do not show edge labels by default; labels appear only on hover/focus
        const showDefaultLabels = false

        const createdConnections = new Set<string>()
        const mergedPairKey = (a: string, b: string) => (a < b ? `${a}|${b}` : `${b}|${a}`)
        const pairMap = new Map<string, { aToB?: { online: boolean, rtt: number }, bToA?: { online: boolean, rtt: number } }>()
        let realConnectionCount = 0
        let adjacentConnections = 0
        let centerConnections = 0

        // Debug: Track some example connections
        const debugConnections: Array<{ source: string, target: string, isAdjacent: boolean }> = []

        // Collect node-to-node connections (both directions)
        nodeIds.forEach(sourceNodeId => {
            const nodeAnalysis = network.node_analyses[sourceNodeId]
            const outboundInfo = nodeAnalysis.outbound_info || {}
            Object.keys(outboundInfo).forEach(targetNodeId => {
                if (!nodeIds.includes(targetNodeId)) return
                const connection = outboundInfo[targetNodeId]
                const key = mergedPairKey(sourceNodeId, targetNodeId)
                const rec = pairMap.get(key) || {}
                if (sourceNodeId < targetNodeId) {
                    rec.aToB = { online: connection.status === 'online', rtt: connection.rtt || 0 }
                } else {
                    rec.bToA = { online: connection.status === 'online', rtt: connection.rtt || 0 }
                }
                pairMap.set(key, rec)
            })
        })

        // Emit one edge per bidirectional pair
        for (const [key, rec] of pairMap.entries()) {
            const [a, b] = key.split('|')
            const aNode = nodeMap.get(a)
            const bNode = nodeMap.get(b)
            if (!aNode || !bNode) continue

            const adjacent = isAdjacentByDistance(
                aNode?.position.x || 0,
                aNode?.position.y || 0,
                bNode?.position.x || 0,
                bNode?.position.y || 0,
            )

            if (adjacent) adjacentConnections++
            else centerConnections++

            if (debugConnections.length < 5) {
                debugConnections.push({ source: a, target: b, isAdjacent: adjacent })
            }

            const hasAtoB = rec.aToB !== undefined
            const hasBtoA = rec.bToA !== undefined
            const aOnline = rec.aToB?.online ?? false // A→B
            const bOnline = rec.bToA?.online ?? false // B→A
            const bothOnline = hasAtoB && hasBtoA && aOnline && bOnline
            const bothDown = hasAtoB && hasBtoA && !aOnline && !bOnline
            const partial = hasAtoB && hasBtoA && ((aOnline && !bOnline) || (!aOnline && bOnline))
            const anyOnline = aOnline || bOnline
            const rttA = rec.aToB?.rtt
            const rttB = rec.bToA?.rtt

            // Labels for default (non-hover) rendering
            let labelText: string | undefined = undefined
            if (hasAtoB && hasBtoA) {
                // Default labels are disabled; only show on hover/focus
                const showLabel = (showDefaultLabels && anyOnline)
                if (showLabel) {
                    const left = aOnline && typeof rttA === 'number' ? `${(rttA as number).toFixed(0)}ms` : 'offline'
                    const right = bOnline && typeof rttB === 'number' ? `${(rttB as number).toFixed(0)}ms` : 'offline'
                    labelText = `${left} →  |  ← ${right}`
                }
            } else if (hasAtoB) {
                const showLabel = (showDefaultLabels && (aOnline || !hideOnlineByDefault))
                if (showLabel) {
                    const left = aOnline && typeof rttA === 'number' ? `${(rttA as number).toFixed(0)}ms` : 'offline'
                    labelText = `${left} →`
                }
            } else if (hasBtoA) {
                const showLabel = (showDefaultLabels && (bOnline || !hideOnlineByDefault))
                if (showLabel) {
                    const right = bOnline && typeof rttB === 'number' ? `${(rttB as number).toFixed(0)}ms` : 'offline'
                    labelText = `← ${right}`
                }
            }

            // Stroke rules
            // - Bidirectional both up: solid green
            // - Bidirectional both down: dashed red
            // - Bidirectional partial: green dashed (non-animated)
            // - Unidirectional: solid green if up else solid red
            let strokeColor = '#22c55e'
            let strokeDasharray = '0'
            if (hasAtoB && hasBtoA) {
                if (bothDown) {
                    strokeColor = '#ef4444'
                    strokeDasharray = '6,3'
                } else if (partial) {
                    // Yellow dashed for degraded (one-way down)
                    strokeColor = '#eab308'
                    strokeDasharray = '6,3'
                } else if (bothOnline) {
                    strokeColor = '#22c55e'
                    strokeDasharray = '0'
                }
            } else if (hasAtoB) {
                strokeColor = aOnline ? '#22c55e' : '#ef4444'
                strokeDasharray = '0'
            } else if (hasBtoA) {
                strokeColor = bOnline ? '#22c55e' : '#ef4444'
                strokeDasharray = '0'
            }

            // Stroke width based on best available RTT for aesthetics
            const rttForStrength = (aOnline ? (rttA ?? 0) : Infinity) < (bOnline ? (rttB ?? 0) : Infinity)
                ? (aOnline ? (rttA ?? 0) : (bOnline ? (rttB ?? 0) : 0))
                : (bOnline ? (rttB ?? 0) : (aOnline ? (rttA ?? 0) : 0))
            const strength = anyOnline ? Math.max(1, 5 - ((rttForStrength as number) / 50)) : 0.5
            const baseStrokeWidth = Math.max(1.5, Math.min(4, strength))
            const strokeWidth = adjacent ? baseStrokeWidth : baseStrokeWidth * 0.8
            const computedOpacity = anyOnline ? (adjacent ? 0.9 : 0.7) : 0.6
            // Hide behavior:
            // - Bidirectional: hide only when both directions are online (fully healthy)
            // - Unidirectional: hide when that single direction is online
            const baseOpacity = (hasAtoB && hasBtoA)
                ? (bothOnline && hideOnlineByDefault ? 0 : computedOpacity)
                : ((anyOnline && hideOnlineByDefault) ? 0 : computedOpacity)

            // Precompute a full label string for hover regardless of default visibility
            const fmtMs = (v?: number) => (typeof v === 'number' && isFinite(v)) ? `${Math.round(v)}ms` : 'offline'
            const fullLabelText: string | undefined = (() => {
                if (hasAtoB && hasBtoA) {
                    const left = aOnline ? fmtMs(rttA) : 'offline'
                    const right = bOnline ? fmtMs(rttB) : 'offline'
                    return `${left} →  |  ← ${right}`
                } else if (hasAtoB) {
                    return aOnline ? `${fmtMs(rttA)} →` : '→ offline'
                } else if (hasBtoA) {
                    return bOnline ? `← ${fmtMs(rttB)}` : 'offline ←'
                }
                return undefined
            })()

            // Orient path so animation flows from the alive direction toward its arrowhead
            // - If only A->B is up, keep a->b
            // - If only B->A is up, flip to b->a
            // - If only one physical direction exists, orient to that direction
            let orientedSource = a
            let orientedTarget = b
            if (partial) {
                if (aOnline && !bOnline) { orientedSource = a; orientedTarget = b }
                else if (bOnline && !aOnline) { orientedSource = b; orientedTarget = a }
            } else if (hasAtoB && !hasBtoA) {
                orientedSource = a; orientedTarget = b
            } else if (!hasAtoB && hasBtoA) {
                orientedSource = b; orientedTarget = a
            }

            const isUnidirectional = (hasAtoB && !hasBtoA) || (!hasAtoB && hasBtoA)
            const canAnimate = partial || isUnidirectional
            // Only animate at creation if the selector is set to 'always'.
            // Hover/Never modes start non-animated; hover/focus recomputes will add animation as needed.
            const isAnimatedNow = (animationMode === 'always') ? !!canAnimate : false
            edges.push({
                id: `${a}-${b}`,
                source: orientedSource,
                sourceHandle: 's',
                target: orientedTarget,
                targetHandle: 't',
                style: {
                    stroke: strokeColor,
                    strokeWidth,
                    // If the edge is animated, include dash + animation so stripes flow
                    ...(isAnimatedNow ? { strokeDasharray: '8 4', animation: 'dashdraw 1s linear infinite' } : { strokeDasharray }),
                    opacity: baseOpacity,
                },
                label: labelText,
                labelStyle: labelText ? {
                    fontSize: 11,
                    fontWeight: '600',
                    fill: bothOnline ? '#16a34a' : (bothDown ? '#ef4444' : (partial ? '#eab308' : (strokeColor === '#22c55e' ? '#16a34a' : (strokeColor === '#eab308' ? '#eab308' : '#ef4444')))),
                    background: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                    padding: '2px 6px',
                    borderRadius: '12px',
                    border: bothOnline ? '1px solid #22c55e' : (bothDown ? '1px solid #ef4444' : (partial ? '1px solid #eab308' : (strokeColor === '#22c55e' ? '1px solid #22c55e' : (strokeColor === '#eab308' ? '1px solid #eab308' : '1px solid #ef4444')))),
                } : undefined,
                labelBgStyle: labelText ? {
                    fill: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                    fillOpacity: 0.9,
                } : undefined,
                data: {
                    isOnline: anyOnline,
                    isMonitorEdge: false,
                    canAnimate,
                    originalLabel: fullLabelText,
                    originalLabelStyle: fullLabelText ? {
                        fontSize: 11,
                        fontWeight: '600',
                        fill: bothOnline ? '#16a34a' : (bothDown ? '#ef4444' : (partial ? '#eab308' : (strokeColor === '#22c55e' ? '#16a34a' : (strokeColor === '#eab308' ? '#eab308' : '#ef4444')))),
                        background: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                        padding: '2px 6px',
                        borderRadius: '12px',
                        border: bothOnline ? '1px solid #22c55e' : (bothDown ? '1px solid #ef4444' : (partial ? '1px solid #eab308' : (strokeColor === '#22c55e' ? '1px solid #22c55e' : (strokeColor === '#eab308' ? '1px solid #eab308' : '1px solid #ef4444')))),
                    } : undefined,
                    originalLabelBgStyle: fullLabelText ? {
                        fill: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                        fillOpacity: 0.9,
                    } : undefined,
                    originalOpacity: computedOpacity,
                    baseOpacity,
                    aToBOnline: aOnline,
                    bToAOnline: bOnline,
                    hasAtoB,
                    hasBtoA,
                },
                // Animation only for fully healthy (solid green) bidirectional links
                animated: isAnimatedNow,
                type: 'floating',
                // Arrowheads: show only for existing directions. Colors reflect that direction's status.
                // Determine which logical directions exist relative to oriented source/target
                markerStart: (() => {
                    // start arrow exists if there is a link from target->source (points back to source)
                    const backOnline = (orientedSource === a) ? bOnline : aOnline
                    const exist = (orientedSource === a) ? hasBtoA : hasAtoB
                    return exist ? {
                        type: MarkerType.ArrowClosed,
                        color: backOnline ? '#22c55e' : '#ef4444',
                        width: 12,
                        height: 12,
                    } : undefined
                })(),
                markerEnd: (() => {
                    // end arrow exists if there is a link from source->target (points toward target)
                    const fwdOnline = (orientedSource === a) ? aOnline : bOnline
                    const exist = (orientedSource === a) ? hasAtoB : hasBtoA
                    return exist ? {
                        type: MarkerType.ArrowClosed,
                        color: fwdOnline ? '#22c55e' : '#ef4444',
                        width: 12,
                        height: 12,
                    } : undefined
                })(),
            })

            createdConnections.add(`${a}-${b}`)
            realConnectionCount++
        }

        // Create connections from nodes to monitors
        nodeIds.forEach(sourceNodeId => {
            monitorIds.forEach(monitorId => {
                const inbound = network.monitor_analyses![monitorId].inbound_info[sourceNodeId]
                if (!inbound) return

                const isOnline = inbound.status === 'online'
                const rtt = inbound.rtt || 0

                // Get positions
                const sourceNode = nodeMap.get(sourceNodeId)
                const targetMonitor = nodeMap.get(monitorId)
                const adjacent = isAdjacentByDistance(
                    sourceNode?.position.x || 0,
                    sourceNode?.position.y || 0,
                    targetMonitor?.position.x || 0,
                    targetMonitor?.position.y || 0,
                )

                if (adjacent) adjacentConnections++
                else centerConnections++

                const strength = isOnline ? Math.max(1, 5 - (rtt / 50)) : 0.5
                const baseStrokeWidth = Math.max(1.5, Math.min(4, strength))
                const strokeWidth = adjacent ? baseStrokeWidth : baseStrokeWidth * 0.8
                const computedOpacity = isOnline ? (adjacent ? 0.9 : 0.7) : 0.6
                const baseOpacity = isOnline && hideOnlineByDefault ? 0 : computedOpacity

                const edgeId = `${sourceNodeId}-${monitorId}`
                const canAnimateMon = true
                const isAnimatedNowMon = (animationMode === 'always') ? true : false
                edges.push({
                    id: edgeId,
                    source: sourceNodeId,
                    sourceHandle: 's',
                    target: monitorId,
                    targetHandle: 't',
                    style: {
                        stroke: isOnline ? '#a855f7' : '#ef4444', // Purple for monitor connections
                        strokeWidth,
                        ...(isAnimatedNowMon ? { strokeDasharray: '8 4', animation: 'dashdraw 1s linear infinite' } : { strokeDasharray: isOnline ? '0' : '6,3' }),
                        opacity: baseOpacity,
                    },
                    label: isOnline && showDefaultLabels ? `${rtt.toFixed(0)}ms` : undefined,
                    labelStyle: isOnline && showDefaultLabels ? {
                        fontSize: 11,
                        fontWeight: '600',
                        fill: '#9333ea',
                        background: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                        padding: '2px 6px',
                        borderRadius: '12px',
                        border: '1px solid #a855f7',
                    } : undefined,
                    labelBgStyle: isOnline && showDefaultLabels ? {
                        fill: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                        fillOpacity: 0.9,
                    } : undefined,
                    data: {
                        isOnline: isOnline,
                        isMonitorEdge: true,
                        canAnimate: canAnimateMon,
                        originalLabel: isOnline ? `${rtt.toFixed(0)}ms` : undefined,
                        originalLabelStyle: isOnline ? {
                            fontSize: 11,
                            fontWeight: '600',
                            fill: '#9333ea',
                            background: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                            padding: '2px 6px',
                            borderRadius: '12px',
                            border: '1px solid #a855f7',
                        } : undefined,
                        originalLabelBgStyle: isOnline ? {
                            fill: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.9)',
                            fillOpacity: 0.9,
                        } : undefined,
                        originalOpacity: computedOpacity,
                        baseOpacity,
                    },
                    animated: isAnimatedNowMon,
                    type: 'floating',
                    markerEnd: {
                        type: MarkerType.ArrowClosed,
                        color: isOnline ? '#a855f7' : '#ef4444',
                        width: 12,
                        height: 12,
                    },
                })

                createdConnections.add(edgeId)
                realConnectionCount++
            })
        })

        DEBUG && console.log(`Created ${realConnectionCount} authentic connections (node-to-node + node-to-monitor)`)
        DEBUG && console.log(`Connection types: ${adjacentConnections} adjacent (face-to-face), ${centerConnections} center-oriented`)
        DEBUG && console.log(`Sample face-to-face connections:`, debugConnections.filter(c => c.isAdjacent))

        DEBUG && console.log('Generated edges:', edges)
        const t1 = performance.now()
        logPerf('processGraph:end', { nodes: nodes.length, edges: edges.length, ms: Math.round(t1 - t0) })
        return { processedNodes: nodes, processedEdges: edges }
    }, [networkData, selectedNetwork, isDark, layoutMode, hideOnlineByDefault, animationMode])

    // Update nodes and edges when processed data changes
    // Important: Set nodes first, then edges to avoid React Flow edge creation errors
    useEffect(() => {
        // When in focus mode, skip the base node reset to avoid briefly showing the unfocused layout.
        if (focusedNodeId) return
        logPerf('setNodes', processedNodes.length)
        setNodes(processedNodes)
    }, [processedNodes, setNodes, focusedNodeId])

    useEffect(() => {
        // When in focus mode, skip the base edge reset to avoid showing all connections.
        if (focusedNodeId) return
        // Only set edges after nodes are updated to avoid React Flow errors
        if (processedNodes.length > 0) {
            // Small delay to ensure React Flow has processed the nodes
            const timer = setTimeout(() => {
                // Filter out edges that would be fully hidden to reduce DOM work
                const renderedEdges = processedEdges.filter(e => {
                    const opacity = e.style?.opacity
                    const hasOpacity = typeof opacity === 'number'
                    const isVisible = hasOpacity ? opacity! > 0.02 : true
                    // If label is hidden and opacity ~0, skip mounting
                    const hasLabel = !!e.label
                    return isVisible || hasLabel
                })
                logPerf('setEdges', { total: processedEdges.length, rendered: renderedEdges.length })
                setEdges(renderedEdges)
            }, 100)
            return () => clearTimeout(timer)
        } else {
            logPerf('clearEdges')
            setEdges([])
        }
    }, [processedEdges, processedNodes.length, setEdges, focusedNodeId])

    // Layout with ELK to reduce crossings and avoid edges over nodes
    useEffect(() => {
        if (layoutMode !== 'elk') return
        let cancelled = false
        const runLayout = async () => {
            if (processedNodes.length === 0) return
            const t0 = performance.now()
            logPerf('elk:start')
            const { default: ELK } = await import('elkjs/lib/elk.bundled.js')
            const elk = new ELK()

            // Match ELK node sizes to our actual circle diameters (estimate from labels)
            const estimate = (id?: string) => estimateDiameterFromLabel(id || '')
            const children = processedNodes.map(n => ({
                id: n.id,
                width: estimate(n.id),
                height: estimate(n.id),
            }))
            const edges = processedEdges.map(e => ({ id: e.id, sources: [e.source], targets: [e.target] }))
            const graph = {
                id: 'root',
                layoutOptions: {
                    // Layered tends to be more stable/compact than force
                    'elk.algorithm': 'layered',
                    'elk.direction': 'RIGHT',
                    // Increase spacing with larger nodes
                    // Tripled spacing for stacked layout
                    'elk.spacing.nodeNode': '240',
                    'elk.spacing.edgeNode': '120',
                    'elk.spacing.edgeEdge': '90',
                    'elk.layered.mergeEdges': 'true',
                    'elk.layered.considerModelOrder': 'true',
                },
                children,
                edges,
            }
            try {
                const res = await elk.layout(graph as any)
                if (cancelled) return
                const laidChildren = (res.children || []) as Array<{ id: string, x: number, y: number, width: number, height: number }>

                // Convert ELK top-left to React Flow center (nodeOrigin = [0.5, 0.5])
                const centers = laidChildren.map(c => ({ id: c.id, cx: c.x + c.width / 2, cy: c.y + c.height / 2 }))
                // Normalize to center around (0,0) so it doesn't appear off-screen/huge
                const minX = Math.min(...centers.map(c => c.cx))
                const maxX = Math.max(...centers.map(c => c.cx))
                const minY = Math.min(...centers.map(c => c.cy))
                const maxY = Math.max(...centers.map(c => c.cy))
                const normCx = (minX + maxX) / 2
                const normCy = (minY + maxY) / 2
                const pos = new Map<string, { x: number, y: number }>(centers.map(c => [c.id, { x: c.cx - normCx, y: c.cy - normCy }]))

                setNodes(curr => curr.map(n => pos.has(n.id) ? { ...n, position: pos.get(n.id)! } : n))
                const t1 = performance.now()
                logPerf('elk:end', { nodes: processedNodes.length, edges: processedEdges.length, ms: Math.round(t1 - t0) })
            } catch (e) {
                // Fallback silently if layout fails
            }
        }
        runLayout()
        return () => {
            cancelled = true
        }
    }, [processedNodes, processedEdges, setNodes, layoutMode])

    // Precompute adjacency for fast hover updates (computed after processedEdges exists)
    const { nodeToEdgesMap, nodeToNeighborsMap } = useMemo(() => {
        const edgeMap = new Map<string, Set<string>>()
        const neighborMap = new Map<string, Set<string>>()
        processedEdges.forEach((edge) => {
            // Map node -> edge ids
            if (!edgeMap.has(edge.source)) edgeMap.set(edge.source, new Set())
            if (!edgeMap.has(edge.target)) edgeMap.set(edge.target, new Set())
            edgeMap.get(edge.source)!.add(edge.id)
            edgeMap.get(edge.target)!.add(edge.id)

            // Map node -> neighbor nodes
            if (!neighborMap.has(edge.source)) neighborMap.set(edge.source, new Set())
            if (!neighborMap.has(edge.target)) neighborMap.set(edge.target, new Set())
            neighborMap.get(edge.source)!.add(edge.target)
            neighborMap.get(edge.target)!.add(edge.source)
        })
        return { nodeToEdgesMap: edgeMap, nodeToNeighborsMap: neighborMap }
    }, [processedEdges])

    // Update nodes and edges based on hover state without triggering viewport reset
    useEffect(() => {
        // If we're in focus mode, skip hover-driven updates
        if (focusedNodeId) return
        if (isDragging) return // skip hover updates while dragging to reduce churn
        if (isPanning) return // skip hover updates while panning the viewport
        const largePerfGraph = processedNodes.length > 120
        if (!hoveredNode) {
            logPerf('hover:none:reset')
            // Reset all nodes and edges to normal state
            if (!largePerfGraph) {
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
            }
            // Recompute which edges to mount based on visibility
            const recomputed = processedEdges.map(e => {
                const baseOpacity = (e.data && (e.data as any).baseOpacity) ?? ((e.data && (e.data as any).originalOpacity) ?? 0.6)
                const shouldShowDefaultLabel = ((processedNodes.length <= 35) && (zoom >= 0.9) && !hideOnlineByDefault) && !!e.data?.originalLabel && baseOpacity > 0
                const baseCanAnim = (e.data as any)?.canAnimate
                const baseAnimated = (animationMode === 'always') && !!baseCanAnim
                return {
                    ...e,
                    // Reset to base styles and animation state when not hovering
                    animated: baseAnimated,
                    style: { ...(e.style || {}), opacity: baseOpacity, strokeWidth: (e.style as any)?.strokeWidth, transition: 'opacity 300ms ease, stroke-width 200ms ease', ...(baseAnimated ? { strokeDasharray: '8 4', animation: 'dashdraw 1s linear infinite' } : { strokeDasharray: (e.style as any)?.strokeDasharray, animation: undefined }) },
                    label: (shouldShowDefaultLabel) ? e.data?.originalLabel : undefined,
                    labelStyle: (shouldShowDefaultLabel) ? e.data?.originalLabelStyle : undefined,
                    labelBgStyle: (shouldShowDefaultLabel) ? e.data?.originalLabelBgStyle : undefined
                }
            })
            const filtered = recomputed.filter(e => {
                const op = e.style?.opacity
                const visible = typeof op === 'number' ? op > 0.02 : true
                return visible || !!e.label
            })
            setEdges(filtered)
        } else {
            // Find connected nodes and edges using precomputed maps
            const connectedNodeIds = new Set<string>([hoveredNode])
            const relevantEdgeIds = new Set<string>(nodeToEdgesMap.get(hoveredNode) || [])
            // Allow hover labels even in performance mode to expose online connections
            const enableHoverLabels = true
            logPerf('hover:update', { node: hoveredNode, edges: relevantEdgeIds.size })
            const neighbors = nodeToNeighborsMap.get(hoveredNode)
            if (neighbors) {
                neighbors.forEach(n => connectedNodeIds.add(n))
            }

            // Update nodes with hover state only if changes are needed (skip for very large graphs in performance mode)
            if (!largePerfGraph) {
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
            }

            // Update edges with hover state only if changes are needed
            // Recompute from canonical edges to ensure relevant hidden edges are mounted
            const recomputed = processedEdges.map(e => {
                const isRelevant = relevantEdgeIds.has(e.id)
                const hoverOpacity = (e.data && (e.data as any).originalOpacity) ?? (e.animated ? 0.9 : 0.6)
                // In performance mode, default labels are hidden, but on hover we still raise opacity and can show labels if desired
                const targetOpacity = isRelevant ? hoverOpacity : 0
                const shouldShowLabel = enableHoverLabels && isRelevant && e.data?.originalLabel
                const baseSW = (e.style as any)?.strokeWidth ?? 2
                const canAnim = (e.data as any)?.canAnimate
                const animatedFlag = (animationMode === 'never') ? false :
                    (animationMode === 'hover') ? (isRelevant && !!canAnim) :
                        (animationMode === 'always') ? (!!canAnim) : false
                return {
                    ...e,
                    // Animate hovered edges with flowing effect and slightly thicker stroke
                    animated: animatedFlag,
                    style: { ...(e.style || {}), opacity: targetOpacity, strokeWidth: isRelevant ? Math.min(4, baseSW + 0.8) : baseSW, transition: 'opacity 250ms ease, stroke-width 200ms ease', ...(animatedFlag ? { strokeDasharray: '8 4', animation: 'dashdraw 1s linear infinite' } : {}) },
                    label: shouldShowLabel ? e.data?.originalLabel : undefined,
                    labelStyle: shouldShowLabel ? e.data?.originalLabelStyle : undefined,
                    labelBgStyle: shouldShowLabel ? e.data?.originalLabelBgStyle : undefined
                }
            })
            const filtered = recomputed.filter(e => {
                const op = e.style?.opacity
                const visible = typeof op === 'number' ? op > 0.02 : true
                return visible || !!e.label
            })
            setEdges(filtered)
        }
    }, [hoveredNode, setNodes, setEdges, nodeToEdgesMap, nodeToNeighborsMap, isDragging, isPanning, processedNodes.length, zoom, hideOnlineByDefault, focusedNodeId, animationMode])

    // Focus mode: center a node and arrange its neighbors around it, dim others, and show only its edges with labels
    // Remember viewport before entering focus so we can restore it on exit
    const prevViewportRef = useRef<{ x: number; y: number; zoom: number } | null>(null)
    // No removal timer; we keep hidden nodes mounted to allow smooth exit animations

    const clearFocus = useCallback(() => {
        setFocusedNodeId(null)
        // Restore all nodes with a staged animation back to their original positions
        const posMap = new Map<string, { x: number; y: number }>(processedNodes.map(n => [n.id, n.position]))
        // Stage 1: add transitions to all currently mounted nodes
        setNodes(curr => curr.map(n => ({
            ...n,
            // Enable transform + opacity transitions
            style: { ...(n.style || {}), transition: 'transform 450ms ease, opacity 350ms ease', pointerEvents: 'auto' as any },
            data: { ...n.data, isHighlighted: false, isDimmed: false },
        })))
        // Stage 2 (next frame): move to original positions and fade in
        requestAnimationFrame(() => {
            setNodes(curr => curr.map(n => ({
                ...n,
                position: posMap.get(n.id) ?? n.position,
                style: { ...(n.style || {}), opacity: 1, pointerEvents: 'auto' as any },
                data: { ...n.data, isHighlighted: false, isDimmed: false },
            })))

            // After the animation completes, remove transitions so normal dragging isn't animated
            const CLEANUP_DELAY_MS = 500
            setTimeout(() => {
                setNodes(curr => curr.map(n => {
                    const { transition, ...rest } = (n.style || {}) as any
                    return {
                        ...n,
                        style: { ...rest, pointerEvents: 'auto' as any },
                    }
                }))
            }, CLEANUP_DELAY_MS)
        })
        // Restore edges to base opacity and default label policy
        const recomputed = processedEdges.map(e => {
            const baseOpacity = (e.data && (e.data as any).baseOpacity) ?? ((e.data && (e.data as any).originalOpacity) ?? (e.animated ? 0.9 : 0.6))
            const shouldShowDefaultLabel = ((processedNodes.length <= 35) && (zoom >= 0.9) && !hideOnlineByDefault) && !!e.data?.originalLabel && baseOpacity > 0
            const canAnim = (e.data as any)?.canAnimate
            const animatedFlag = (animationMode === 'never') ? false :
                (animationMode === 'always') ? (!!canAnim) :
                    false
            return {
                ...e,
                animated: animatedFlag,
                style: { ...(e.style || {}), opacity: baseOpacity, strokeWidth: (e.style as any)?.strokeWidth ?? 2, transition: 'opacity 350ms ease, stroke-width 200ms ease' },
                label: (shouldShowDefaultLabel) ? e.data?.originalLabel : undefined,
                labelStyle: (shouldShowDefaultLabel) ? e.data?.originalLabelStyle : undefined,
                labelBgStyle: (shouldShowDefaultLabel) ? e.data?.originalLabelBgStyle : undefined
            }
        })
        const filtered = recomputed.filter(e => {
            const op = e.style?.opacity
            const visible = typeof op === 'number' ? op > 0.02 : true
            return visible || !!e.label
        })
        setEdges(filtered)
        // Restore previous viewport if we saved one when entering focus, else fit full graph
        try {
            const inst = reactFlowRef.current
            if (inst) {
                const prev = prevViewportRef.current
                // Wait a frame so restored nodes are mounted before viewport change
                requestAnimationFrame(() => {
                    try {
                        if (prev) {
                            // Animate back to saved viewport
                            // @ts-ignore - some versions allow a second options arg for duration
                            inst.setViewport(prev, { duration: 600 })
                        } else {
                            inst.fitView({ duration: 400, padding: 0.2 })
                        }
                    } catch { }
                })
            }
        } catch { }
        // Clear saved viewport after restoring
        prevViewportRef.current = null
    }, [processedNodes, processedEdges, setNodes, setEdges, reactFlowRef, zoom, hideOnlineByDefault, animationMode])

    const focusNode = useCallback((centerId: string, force: boolean = false) => {
        if (!processedNodes.length) return
        // Prevent spamming while an animation/layout is in progress
        if (focusingRef.current) return
        // If we're already focused on this node, do nothing
        if (!force && focusedNodeId === centerId) return
        focusingRef.current = true
        // Save current viewport once when entering focus mode
        try {
            if (!focusedNodeId) {
                const inst = reactFlowRef.current as ReactFlowInstance | null
                if (inst && (prevViewportRef.current == null)) {
                    // Prefer getViewport if available, else fallback to composing from current transform
                    // @ts-ignore - older types may not declare getViewport
                    const vp = inst.getViewport ? inst.getViewport() : { x: 0, y: 0, zoom: inst.getZoom ? inst.getZoom() : 1 }
                    prevViewportRef.current = vp
                }
            }
        } catch { }
        setFocusedNodeId(centerId)

        // Determine neighbors of the focused node
        const neighborSet = new Set<string>(nodeToNeighborsMap.get(centerId) || [])
        // Place focused at center and neighbors around a circle
        const N = neighborSet.size
        const radius = Math.max(320, Math.min(800, 140 + N * 40))
        // Sort neighbors by current polar angle around the focus to keep relative order
        const centerNode = processedNodes.find(n => n.id === centerId)
        const cx0 = centerNode?.position.x || 0
        const cy0 = centerNode?.position.y || 0
        const neighborsOrdered = Array.from(neighborSet)
            .map(id => {
                const n = processedNodes.find(nn => nn.id === id)
                const dx = (n?.position.x || 0) - cx0
                const dy = (n?.position.y || 0) - cy0
                const ang = Math.atan2(dy, dx)
                return { id, ang }
            })
            .sort((a, b) => a.ang - b.ang)
            .map(x => x.id)

        // Precompute target positions for focus layout
        const targetPos = new Map<string, { x: number; y: number }>()
        targetPos.set(centerId, { x: 0, y: 0 })
        neighborsOrdered.forEach((id, idx) => {
            const angle = (idx / Math.max(1, N)) * Math.PI * 2
            targetPos.set(id, { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius })
        })
        // Stage 1: add transition styles and set visibility flags without moving yet
        setNodes(curr => curr.map(n => {
            const isFocusOrNeighbor = n.id === centerId || neighborSet.has(n.id)
            return {
                ...n,
                style: { ...(n.style || {}), transition: 'transform 450ms ease, opacity 300ms ease', opacity: isFocusOrNeighbor ? 1 : 0, pointerEvents: isFocusOrNeighbor ? (n.style as any)?.pointerEvents : ('none' as any) },
                data: { ...n.data, isHighlighted: isFocusOrNeighbor, isDimmed: !isFocusOrNeighbor },
            }
        }))
        // Stage 2 (next frame): move focus + neighbors to target positions
        requestAnimationFrame(() => {
            setNodes(curr => curr.map(n => ({
                ...n,
                position: targetPos.get(n.id) ?? n.position,
            })))
        })

        // Update edges: show only those connected to the focus, with labels
        const relevantEdgeIds = new Set<string>(nodeToEdgesMap.get(centerId) || [])
        const recomputed = processedEdges.map(e => {
            const isRelevant = relevantEdgeIds.has(e.id)
            const hoverOpacity = (e.data && (e.data as any).originalOpacity) ?? (e.animated ? 0.9 : 0.6)
            const targetOpacity = isRelevant ? hoverOpacity : 0
            const shouldShowLabel = isRelevant && e.data?.originalLabel
            const baseSW = (e.style as any)?.strokeWidth ?? 2
            const canAnim = (e.data as any)?.canAnimate
            const animatedFlag = (animationMode === 'never') ? false :
                (animationMode === 'hover') ? (isRelevant && !!canAnim) :
                    (animationMode === 'always') ? (!!canAnim) : false
            return {
                ...e,
                animated: animatedFlag,
                style: { ...(e.style || {}), opacity: targetOpacity, strokeWidth: isRelevant ? Math.min(4, baseSW + 0.8) : baseSW, transition: 'opacity 350ms ease, stroke-width 200ms ease', ...(animatedFlag ? { strokeDasharray: '8 4', animation: 'dashdraw 1s linear infinite' } : {}) },
                label: shouldShowLabel ? e.data?.originalLabel : undefined,
                labelStyle: shouldShowLabel ? e.data?.originalLabelStyle : undefined,
                labelBgStyle: shouldShowLabel ? e.data?.originalLabelBgStyle : undefined
            }
        })
        const filtered = recomputed.filter(e => {
            const op = e.style?.opacity
            const visible = typeof op === 'number' ? op > 0.02 : true
            return visible || !!e.label
        })
        setEdges(filtered)

        // Animate viewport to fit all focused nodes (focused + neighbors)
        try {
            const inst = reactFlowRef.current
            if (inst) {
                // Wait a frame so the node list change is applied before fitting
                requestAnimationFrame(() => {
                    try {
                        inst.fitView({ duration: 600, padding: 0.2 })
                    } catch { }
                })
            }
        } catch { }
        focusingRef.current = false
    }, [processedNodes, processedEdges, nodeToNeighborsMap, setNodes, setEdges, focusedNodeId, animationMode])

    // Keep focus edges/nodes consistent if data refreshes or animation mode changes while focused
    useEffect(() => {
        if (!focusedNodeId) return
        // Reapply focus layout and edge states without exiting
        focusNode(focusedNodeId, true)
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [processedNodes, processedEdges, animationMode])

    // Track zoom to gate default labels progressively (throttled to animation frame)
    const zoomRaf = useRef<number | null>(null)
    const pendingZoom = useRef<number | null>(null)
    const lastZoom = useRef<number>(1)
    const handleMove = useCallback((_e: any, viewport: { zoom: number }) => {
        const z = viewport.zoom
        // Only update zoom state when change is noticeable (reduces re-renders when panning)
        if (Math.abs(z - lastZoom.current) < 0.05) return
        lastZoom.current = z
        pendingZoom.current = z
        if (zoomRaf.current !== null) return
        zoomRaf.current = requestAnimationFrame(() => {
            zoomRaf.current = null
            if (pendingZoom.current != null) setZoom(pendingZoom.current)
        })
    }, [])

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
                        Interactive visualization of mesh network topology • Drag to pan • Scroll to zoom
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
                        onChange={(e) => { setSelectedNetwork(e.target.value); try { localStorage.setItem('meshmon.selectedNetwork', e.target.value) } catch { } }}
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
                    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
                        <div className="h-[calc(100vh-12rem)] min-h-[500px] relative max-h-[calc(100vh-12rem)]">
                            <ReactFlow
                                onInit={(instance) => { reactFlowRef.current = instance }}
                                nodes={nodes}
                                edges={edges}
                                onNodesChange={onNodesChange}
                                onEdgesChange={onEdgesChange}
                                onConnect={onConnect}
                                edgeTypes={edgeTypes}
                                onMove={handleMove}
                                onMoveStart={() => {
                                    setIsPanning(true)
                                    // update node flags quickly without recompute
                                    setNodes(curr => curr.map(n => ({ ...n, data: { ...n.data, isPanning: true } })))
                                }}
                                onMoveEnd={() => {
                                    setIsPanning(false)
                                    setNodes(curr => curr.map(n => ({ ...n, data: { ...n.data, isPanning: false } })))
                                }}
                                nodeTypes={nodeTypes}
                                attributionPosition="bottom-left"
                                className={isDark ? 'dark' : ''}
                                proOptions={{ hideAttribution: true }}
                                defaultEdgeOptions={{
                                    type: 'floating',
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
                                zoomOnDoubleClick={false}
                                minZoom={0.1}
                                maxZoom={3.0}
                                zoomOnPinch={true}
                                nodeOrigin={[0.5, 0.5]}
                                onlyRenderVisibleElements
                                onNodeDoubleClick={(_e, node) => {
                                    if (focusedNodeId === node.id) {
                                        clearFocus()
                                    } else {
                                        focusNode(node.id)
                                    }
                                }}
                                onPaneClick={(e: any) => { if (focusedNodeId && e?.detail === 2) clearFocus() }}
                                onNodeDragStart={() => setIsDragging(true)}
                                onNodeDrag={() => setIsDragging(true)}
                                onNodeDragStop={() => setIsDragging(false)}
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
                                {(processedNodes.length <= 30 && processedEdges.length <= 200) && (
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
                                )}
                                <Panel position="top-right" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-3">
                                    <div className="space-y-3 text-xs">
                                        {focusedNodeId && (
                                            <div className="flex justify-between items-center p-2 rounded-md bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800">
                                                <span className="text-amber-700 dark:text-amber-300 font-medium">Focus: {focusedNodeId}</span>
                                                <button
                                                    onClick={clearFocus}
                                                    className="px-2 py-1 text-xs rounded bg-amber-600 text-white hover:bg-amber-700"
                                                >Exit focus</button>
                                            </div>
                                        )}
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
                                                {/* Bidirectional: both up (solid green with arrowheads both ends) */}
                                                <div className="flex items-center space-x-2">
                                                    <svg width="46" height="10" viewBox="0 0 46 10" className="shrink-0">
                                                        <defs>
                                                            <marker id="lg-bidi-up-start" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto-start-reverse">
                                                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e" />
                                                            </marker>
                                                            <marker id="lg-bidi-up-end" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto">
                                                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e" />
                                                            </marker>
                                                        </defs>
                                                        <line x1="6" y1="5" x2="40" y2="5" stroke="#22c55e" strokeWidth="2.5" markerStart="url(#lg-bidi-up-start)" markerEnd="url(#lg-bidi-up-end)" />
                                                    </svg>
                                                    <span className="text-gray-600 dark:text-gray-400">Bidirectional: up</span>
                                                </div>
                                                {/* Bidirectional: degraded (one way down) dashed yellow with red/green arrowheads */}
                                                <div className="flex items-center space-x-2">
                                                    <svg width="46" height="10" viewBox="0 0 46 10" className="shrink-0">
                                                        <defs>
                                                            <marker id="lg-bidi-deg-start" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto-start-reverse">
                                                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                                                            </marker>
                                                            <marker id="lg-bidi-deg-end" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto">
                                                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e" />
                                                            </marker>
                                                        </defs>
                                                        <line x1="6" y1="5" x2="40" y2="5" stroke="#eab308" strokeWidth="2.5" strokeDasharray="6 3" markerStart="url(#lg-bidi-deg-start)" markerEnd="url(#lg-bidi-deg-end)" />
                                                    </svg>
                                                    <span className="text-gray-600 dark:text-gray-400">Bidirectional: degraded (one-way down)</span>
                                                </div>
                                                {/* Bidirectional: down (dashed red with red arrowheads) */}
                                                <div className="flex items-center space-x-2">
                                                    <svg width="46" height="10" viewBox="0 0 46 10" className="shrink-0">
                                                        <defs>
                                                            <marker id="lg-bidi-down-start" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto-start-reverse">
                                                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                                                            </marker>
                                                            <marker id="lg-bidi-down-end" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto">
                                                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                                                            </marker>
                                                        </defs>
                                                        <line x1="6" y1="5" x2="40" y2="5" stroke="#ef4444" strokeWidth="2.5" strokeDasharray="6 3" markerStart="url(#lg-bidi-down-start)" markerEnd="url(#lg-bidi-down-end)" />
                                                    </svg>
                                                    <span className="text-gray-600 dark:text-gray-400">Bidirectional: down</span>
                                                </div>
                                                {/* Unidirectional: up (single green arrowhead) */}
                                                <div className="flex items-center space-x-2">
                                                    <svg width="46" height="10" viewBox="0 0 46 10" className="shrink-0">
                                                        <defs>
                                                            <marker id="lg-uni-up-end" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto">
                                                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e" />
                                                            </marker>
                                                        </defs>
                                                        <line x1="0" y1="5" x2="40" y2="5" stroke="#22c55e" strokeWidth="2.5" markerEnd="url(#lg-uni-up-end)" />
                                                    </svg>
                                                    <span className="text-gray-600 dark:text-gray-400">Unidirectional: up</span>
                                                </div>
                                                {/* Unidirectional: down (single red arrowhead) */}
                                                <div className="flex items-center space-x-2">
                                                    <svg width="46" height="10" viewBox="0 0 46 10" className="shrink-0">
                                                        <defs>
                                                            <marker id="lg-uni-down-end" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto">
                                                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                                                            </marker>
                                                        </defs>
                                                        <line x1="0" y1="5" x2="40" y2="5" stroke="#ef4444" strokeWidth="2.5" markerEnd="url(#lg-uni-down-end)" />
                                                    </svg>
                                                    <span className="text-gray-600 dark:text-gray-400">Unidirectional: down</span>
                                                </div>
                                                <div className="text-[10px] text-gray-500 dark:text-gray-500 pt-0.5">Arrowheads are colored per direction (green = up, red = down).</div>
                                            </div>
                                        </div>
                                        <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                                            <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-1.5">Layout</div>
                                            <div className="flex items-center space-x-2 mb-2">
                                                <label className="text-gray-600 dark:text-gray-400">Layout:</label>
                                                <select
                                                    value={layoutMode}
                                                    onChange={(e) => setLayoutMode(e.target.value as any)}
                                                    className="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                                                >
                                                    <option value="pretty">Golden Spiral</option>
                                                    <option value="concentric">Concentric</option>
                                                    <option value="dense">Dense Grid</option>
                                                    <option value="elk">Stacked</option>
                                                </select>
                                            </div>
                                            <div className="mt-2">
                                                <label className="inline-flex items-center space-x-2 cursor-pointer">
                                                    <input type="checkbox" checked={hideOnlineByDefault} onChange={(e) => setHideOnlineByDefault(e.target.checked)} />
                                                    <span className="text-gray-600 dark:text-gray-400">Hide online edges (show on hover)</span>
                                                </label>
                                            </div>
                                            <div className="mt-2">
                                                <label className="text-gray-600 dark:text-gray-400 mr-2">Animate:</label>
                                                <select
                                                    value={animationMode}
                                                    onChange={(e) => setAnimationMode(e.target.value as any)}
                                                    className="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                                                >
                                                    <option value="never">Never</option>
                                                    <option value="hover">On hover/focus</option>
                                                    <option value="always">Always</option>
                                                </select>
                                            </div>
                                        </div>
                                    </div>
                                </Panel>
                                <Panel position="bottom-right" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-2">
                                    <div className="space-y-1 text-xs">
                                        <div className="font-medium text-gray-900 dark:text-gray-100">Connection Info</div>
                                        <div className="text-gray-600 dark:text-gray-400">Total Nodes: {networks.find(n => n.id === selectedNetwork)?.total_nodes || 0}</div>
                                        <div className="text-gray-600 dark:text-gray-400">Online Nodes: {networks.find(n => n.id === selectedNetwork)?.online_nodes || 0}</div>
                                        <div className="text-gray-600 dark:text-gray-400">Connections: {processedEdges.length}</div>
                                        <div className="text-gray-600 dark:text-gray-400">Shown Connections: {edges.filter(e => (typeof e.style?.opacity === 'number' ? e.style!.opacity! > 0.02 : true) || !!e.label).length}</div>
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
