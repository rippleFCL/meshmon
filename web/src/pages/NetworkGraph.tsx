import { useCallback, useMemo, useState, useEffect, useRef } from 'react'
import ReactFlow, {
    addEdge,
    Connection,
    useNodesState,
    useEdgesState,
    Controls,
    MiniMap,
    Background,
    Panel,
    NodeTypes,
    BackgroundVariant,
    ReactFlowInstance,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { meshmonApi } from '../api'
import { MeshMonApi } from '../types'
import { useTheme } from '../contexts/ThemeContext'
import { useRefresh } from '../contexts/RefreshContext'
import { Activity, Zap, WifiOff } from 'lucide-react'
import FloatingBezierEdge from '../components/graph/FloatingBezierEdge'
import MeshNode from '../components/graph/MeshNode'
import MonitorNode from '../components/graph/MonitorNode'
import { estimateDiameterFromLabel } from '../components/graph/utils'
import GraphLegend from '../components/graph/GraphLegend'
import FocusBanner from '../components/graph/FocusBanner'
import GraphSettings from '../components/graph/GraphSettings'
import GraphStats from '../components/graph/GraphStats'
import { useProcessedGraph } from '../components/graph/hooks/useProcessedGraph'
import { getLayoutEngine } from '../components/graph/layouts'
import { usePositionAnimator } from '../components/graph/hooks/usePositionAnimator'

// Toggle for performance/graph mutation logs
const PERF_LOG = true
let __GRAPH_SEQ = 0
const logPerf = (...args: any[]) => {
    if (PERF_LOG) console.log('[Graph]', ++__GRAPH_SEQ, ...args)
}


const nodeTypes: NodeTypes = {
    meshNode: MeshNode,
    monitorNode: MonitorNode,
}
const edgeTypes = { floating: FloatingBezierEdge }

export default function NetworkGraph() {
    const { isDark } = useTheme()
    const { registerRefreshCallback } = useRefresh()
    const [selectedNetwork, setSelectedNetwork] = useState<string | null>(() => {
        try { return localStorage.getItem('meshmon.selectedNetwork') } catch { return null }
    })
    const [nodes, setNodes, onNodesChange] = useNodesState([])
    const [edges, setEdges, onEdgesChange] = useEdgesState([])
    const [networkData, setNetworkData] = useState<MeshMonApi | null>(null)
    const networks = useMemo(
        () => Object.entries(networkData?.networks || {}).map(([id, info]) => ({ id, name: id, info })),
        [networkData]
    )
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [hoveredNode, setHoveredNode] = useState<string | null>(null)
    const [isDragging, setIsDragging] = useState<boolean>(false)
    const [isPanning, setIsPanning] = useState<boolean>(false)
    const [layoutMode, setLayoutMode] = useState<'forced' | 'concentric' | 'dense' | 'pretty'>(() => {
        try {
            const v = localStorage.getItem('meshmon.layoutMode')
            // Back-compat: treat 'elk' as 'forced'
            const mapped = (v === 'elk') ? 'forced' : v
            return (mapped === 'forced' || mapped === 'concentric' || mapped === 'dense' || mapped === 'pretty') ? (mapped as any) : 'pretty'
        } catch {
            return 'pretty'
        }
    })
    const [hideOnlineByDefault, setHideOnlineByDefault] = useState<boolean>(() => {
        try {
            const v = localStorage.getItem('meshmon.hideOnlineByDefault')
            return v === null ? true : (v === 'true')
        } catch {
            return true
        }
    })
    // Animation policy for edges
    const [animationMode, setAnimationMode] = useState<'never' | 'hover' | 'always'>(() => {
        try {
            const v = localStorage.getItem('meshmon.animationMode')
            return (v === 'never' || v === 'hover' || v === 'always') ? v : 'hover'
        } catch {
            return 'hover'
        }
    })
    const [zoom, setZoom] = useState<number>(1)
    const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null)
    const reactFlowRef = useRef<ReactFlowInstance | null>(null)
    const forcedPosRef = useRef<Map<string, { x: number; y: number }> | null>(null)
    const handleLayoutPositions = useCallback((pos: Map<string, { x: number; y: number }>) => {
        if (focusedNodeId) { logPerf('cb:onLayoutPositions:ignored-during-focus'); return }
        logPerf('cb:onLayoutPositions', { size: pos.size })
        forcedPosRef.current = pos
    }, [focusedNodeId])
    const focusingRef = useRef<boolean>(false)
    const { setNodesRef, animateNodePositions, cancelPositionAnimation } = usePositionAnimator(setNodes)
    useEffect(() => { setNodesRef(nodes) }, [nodes, setNodesRef])

    // Function to handle node hover and update opacity
    // Throttle hover updates to animation frames to avoid excessive re-renders
    const hoverRaf = useRef<number | null>(null)
    const pendingHover = useRef<string | null>(null)
    const handleNodeHover = useCallback((hoveredNodeId: string | null) => {
        logPerf('cb:handleNodeHover', { hoveredNodeId })
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
        logPerf('effect:mount+registerRefresh')
        fetchData()
        registerRefreshCallback(fetchData)
        // Settings are initialized from localStorage in state initializers
    }, [fetchData, registerRefreshCallback])

    // Compute graph model
    const { processedNodes, processedEdges, nodeToEdgesMap, nodeToNeighborsMap } = useProcessedGraph(
        networkData,
        selectedNetwork,
        isDark,
        hideOnlineByDefault,
        animationMode
    )

    // Persist user settings
    useEffect(() => {
        try {
            logPerf('effect:persistSettings', { layoutMode, hideOnlineByDefault, animationMode })
            localStorage.setItem('meshmon.layoutMode', layoutMode)
            localStorage.setItem('meshmon.hideOnlineByDefault', String(hideOnlineByDefault))
            localStorage.setItem('meshmon.animationMode', animationMode)
        } catch { }
    }, [layoutMode, hideOnlineByDefault, animationMode])

    // Pre-compute layout on initial mount/topology/layout change BEFORE rendering
    const [initialLayoutDone, setInitialLayoutDone] = useState(false)
    const topoKey = useMemo(() => ({ n: processedNodes.map(n => n.id).join('|'), e: processedEdges.map(e => e.id).join('|') }), [processedNodes, processedEdges])
    useEffect(() => {
        let cancelled = false
        async function runInitialLayout() {
            // Skip while focused to avoid fighting focus animation
            if (focusedNodeId) return
            // Compute using selected layout and set node positions prior to mounting
            const engine = getLayoutEngine(layoutMode as any)
            try {
                logPerf('layout:initial:start', { layoutMode, nodes: processedNodes.length, edges: processedEdges.length })
                // Hide any previous graph while recomputing
                setNodes([])
                setEdges([])
                const maybe = engine.compute(processedNodes, processedEdges, { isDark })
                const pos = (maybe instanceof Promise) ? await maybe : maybe
                if (cancelled) return
                // Seed nodes with computed positions and attach hover handlers
                const withPos = processedNodes.map(n => ({ ...n, position: pos.get(n.id) ?? n.position, data: { ...n.data, onHover: handleNodeHover, isPanning } } as any))
                setNodes(withPos)
                // Set edges quickly after nodes
                setEdges(processedEdges)
                setInitialLayoutDone(true)
                // Cache forced positions for restore-on-exit-focus
                handleLayoutPositions(pos)
                logPerf('layout:initial:end', { layoutMode })
            } catch (e) {
                console.warn('layout initial failed', e)
                if (!cancelled) {
                    // Fallback: mount processed nodes as-is
                    setNodes(processedNodes.map(n => ({ ...n, data: { ...n.data, onHover: handleNodeHover, isPanning } } as any)))
                    setEdges(processedEdges)
                    setInitialLayoutDone(true)
                }
            }
        }
        // Only run when topology/layout changes or when not yet done for current topo
        setInitialLayoutDone(false)
        runInitialLayout()
        return () => { cancelled = true }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [layoutMode, topoKey.n, topoKey.e, isDark, selectedNetwork])

    // Update nodes when processed node data changes (preserve positions after initial layout)
    // Important: Set nodes independently; edges are handled in a separate effect
    useEffect(() => {
        logPerf('effect:processedNodes->setNodes', { focusedNodeId, count: processedNodes.length, layoutMode, initialLayoutDone })
        // When in focus mode, skip the base node reset to avoid briefly showing the unfocused layout.
        if (focusedNodeId) return
        // Preserve positions; only update data and add/remove nodes as needed
        setNodes((curr) => {
            const currMap = new Map(curr.map(n => [n.id, n]))
            const next = processedNodes.map(pn => {
                const existing = currMap.get(pn.id)
                return {
                    ...pn,
                    position: existing?.position ?? pn.position,
                    data: { ...pn.data, onHover: handleNodeHover, isPanning },
                } as any
            })
            return next
        })
    }, [processedNodes, setNodes, handleNodeHover, isPanning, focusedNodeId, initialLayoutDone, layoutMode])

    // Update edges when processed edges change; filter out fully hidden edges and debounce slightly to avoid thrash
    useEffect(() => {
        // Skip while focused; focus mode manages edges explicitly
        if (focusedNodeId) return
        const timer = setTimeout(() => {
            const renderedEdges = processedEdges.filter(e => {
                const opacity = e.style?.opacity
                const hasOpacity = typeof opacity === 'number'
                const isVisible = hasOpacity ? (opacity as number) > 0.02 : true
                const hasLabel = !!e.label
                return isVisible || hasLabel
            })
            logPerf('setEdges', { total: processedEdges.length, rendered: renderedEdges.length })
            setEdges(renderedEdges)
        }, 100)
        return () => clearTimeout(timer)
    }, [processedEdges, processedNodes.length, setEdges, focusedNodeId])

    // Layout positions are precomputed in the initial layout effect above; do not run layout while focused

    // Adjacency now comes from useProcessedGraph

    // Update nodes and edges based on hover state without triggering viewport reset
    useEffect(() => {
        logPerf('effect:hover', { hoveredNode, isDragging, isPanning, zoom, processedNodes: processedNodes.length })
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
                neighbors.forEach((n: string) => connectedNodeIds.add(n))
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
        logPerf('cb:clearFocus:start')
        // Animate node positions back to forced layout positions if available, else to processed positions
        const posMap = (forcedPosRef.current && forcedPosRef.current.size)
            ? new Map(forcedPosRef.current)
            : new Map<string, { x: number; y: number }>(processedNodes.map(n => [n.id, n.position]))
        cancelPositionAnimation()
        // Stage: update flags and fade in hidden nodes (opacity only)
        setNodes(curr => curr.map(n => ({
            ...n,
            style: { ...(n.style || {}), transition: 'opacity 350ms ease', opacity: 1, pointerEvents: 'auto' as any },
            data: { ...n.data, isHighlighted: false, isDimmed: false },
        })))
        // Animate positions back so edges track with nodes
        animateNodePositions(posMap, 450)
        // After the animation completes, clear focus so base effects resume
        setTimeout(() => {
            // Remove transition styling cleanup
            setNodes(curr => curr.map(n => {
                const { transition, ...rest } = (n.style || {}) as any
                return { ...n, style: { ...rest, pointerEvents: 'auto' as any } }
            }))
            setFocusedNodeId(null)
        }, 500)
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
        logPerf('cb:clearFocus:done')
    }, [processedNodes, processedEdges, setNodes, setEdges, reactFlowRef, zoom, hideOnlineByDefault, animationMode])

    const focusNode = useCallback((centerId: string, forceOrOptions: boolean | { force?: boolean; refit?: boolean; animate?: boolean } = false) => {
        logPerf('cb:focusNode:start', { centerId, forceOrOptions })
        const force = typeof forceOrOptions === 'boolean' ? forceOrOptions : !!forceOrOptions?.force
        const refit = typeof forceOrOptions === 'boolean' ? true : (forceOrOptions?.refit ?? true)
        const animateRequested = typeof forceOrOptions === 'boolean' ? true : (forceOrOptions?.animate ?? true)
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
        // Compute a compact radius based on neighbor node diameters so spacing is tighter
        const neighborDiams = Array.from(neighborSet).map(id => estimateDiameterFromLabel(id))
        const avgDiam = neighborDiams.length ? (neighborDiams.reduce((a, b) => a + b, 0) / neighborDiams.length) : 120
        const gap = Math.max(22, Math.min(48, avgDiam * 0.22))
        const circumferenceNeeded = Math.max(1, N) * (avgDiam + gap)
        // Scale radius: base breathing room (10%) plus additional 15% as requested (~26.5% total)
        const rCirc = (circumferenceNeeded / (2 * Math.PI)) * 1.265
        // Clamp radius so small neighbor counts don't get too tight
        const minRadius = Math.max(260, avgDiam * 1.75)
        const radius = Math.max(minRadius, Math.min(520, rCirc))
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
        // Determine if we should animate positions: only when entering focus from non-focused state
        const shouldAnimatePositions = animateRequested && !focusedNodeId

        cancelPositionAnimation()
        // Stage 1: set visibility and optionally add transition for opacity (not for transform)
        setNodes(curr => curr.map(n => {
            const isFocusOrNeighbor = n.id === centerId || neighborSet.has(n.id)
            const baseStyle = { ...(n.style || {}) }
            const style = shouldAnimatePositions
                ? { ...baseStyle, transition: 'opacity 300ms ease', opacity: isFocusOrNeighbor ? 1 : 0, pointerEvents: isFocusOrNeighbor ? (n.style as any)?.pointerEvents : ('none' as any) }
                : { ...baseStyle, opacity: isFocusOrNeighbor ? 1 : 0, pointerEvents: isFocusOrNeighbor ? (n.style as any)?.pointerEvents : ('none' as any) }
            return {
                ...n,
                style,
                data: { ...n.data, isHighlighted: isFocusOrNeighbor, isDimmed: !isFocusOrNeighbor },
            }
        }))
        // Stage 2: move focus + neighbors to target positions
        if (shouldAnimatePositions) {
            animateNodePositions(targetPos, 450)
        } else {
            setNodes(curr => curr.map(n => ({
                ...n,
                position: targetPos.get(n.id) ?? n.position,
            })))
        }

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

        // Center on the focused node's target position first, then animate viewport to fit focused + neighbors when refit is requested
        if (refit) {
            try {
                const inst = reactFlowRef.current
                if (inst) {
                    const nodesToFit = [{ id: centerId }, ...neighborsOrdered.map(id => ({ id }))]
                    const centerThenFit = (delayMs: number) => {
                        try {
                            // Center on the target position of the focused node with a short animation
                            const tp = targetPos.get(centerId) || { x: 0, y: 0 }
                            // Prefer setCenter if available; it maintains world-coordinate centering
                            // @ts-ignore - older types may not declare setCenter
                            if (inst.setCenter) {
                                // @ts-ignore
                                inst.setCenter(tp.x, tp.y, { duration: 600, zoom: inst.getZoom ? inst.getZoom() : undefined })
                            } else {
                                // Fallback: do nothing; the follow-up fit will position correctly
                            }
                        } catch { }
                        setTimeout(() => {
                            try { inst.fitView({ nodes: nodesToFit as any, duration: 600, padding: 0.12 }) } catch { }
                        }, Math.max(0, delayMs))
                    }
                    if (shouldAnimatePositions) {
                        // Start fit after positions animate to avoid double zoom; include origin center first
                        centerThenFit(400)
                    } else {
                        // No node animation: center then fit immediately next frame
                        requestAnimationFrame(() => centerThenFit(0))
                    }
                }
            } catch { }
        }
        focusingRef.current = false
        logPerf('cb:focusNode:done', { centerId })
    }, [processedNodes, processedEdges, nodeToNeighborsMap, setNodes, setEdges, focusedNodeId, animationMode])

    // Keep focus edges/nodes consistent if data refreshes or animation mode changes while focused
    useEffect(() => {
        if (!focusedNodeId) return
        logPerf('effect:focusConsistency', { focusedNodeId })
        // Reapply focus layout and edge states without exiting or refitting viewport; do not animate while in focus
        focusNode(focusedNodeId, { force: true, refit: false, animate: false })
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

    // Auto-select first network if none selected; also clear selection if it no longer exists
    useEffect(() => {
        logPerf('effect:autoSelectNetwork', { networks: networks.length, selectedNetwork })
        if (!networks.length) return
        if (!selectedNetwork) {
            setSelectedNetwork(networks[0].id)
            return
        }
        if (!networks.some(n => n.id === selectedNetwork)) {
            setSelectedNetwork(networks[0].id)
        }
    }, [networks, selectedNetwork])

    const onConnect = useCallback(
        (params: Connection) => { logPerf('cb:onConnect', params); setEdges((eds) => addEdge(params, eds)) },
        [setEdges]
    )
    const handleSelectNetwork = useCallback((e: React.ChangeEvent<HTMLSelectElement>) => {
        const v = e.target.value
        logPerf('cb:selectNetwork', { value: v })
        setSelectedNetwork(v)
        try { localStorage.setItem('meshmon.selectedNetwork', v) } catch { }
    }, [])

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

    if (!networkData || networks.length === 0) {
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
                        onChange={handleSelectNetwork}
                        className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                    >
                        {networks.map((network) => {
                            const total = Object.keys(network.info?.nodes || {}).length
                            const online = Object.values(network.info?.nodes || {}).filter((n: any) => n.status === 'online').length
                            return (
                                <option key={network.id} value={network.id}>
                                    {network.name} ({online}/{total} online)
                                </option>
                            )
                        })}
                    </select>
                </div>
            </div>

            {selectedNetwork && (
                <>
                    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
                        <div className="h-[calc(100vh-12rem)] min-h-[500px] relative max-h-[calc(100vh-12rem)]">
                            {!initialLayoutDone && (
                                <div className="absolute inset-0 flex items-center justify-center z-10">
                                    <div className="px-3 py-2 text-sm rounded-md bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-200 border border-gray-300 dark:border-gray-600">
                                        Computing {layoutMode} layout…
                                    </div>
                                </div>
                            )}
                            {initialLayoutDone && (
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
                                        logPerf('rf:onMoveStart')
                                        setIsPanning(true)
                                        // update node flags quickly without recompute
                                        setNodes(curr => curr.map(n => ({ ...n, data: { ...n.data, isPanning: true } })))
                                    }}
                                    onMoveEnd={() => {
                                        logPerf('rf:onMoveEnd')
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
                                    onNodeDragStart={() => { logPerf('rf:onNodeDragStart'); setIsDragging(true) }}
                                    onNodeDrag={() => { /* noisy */ setIsDragging(true) }}
                                    onNodeDragStop={() => { logPerf('rf:onNodeDragStop'); setIsDragging(false) }}
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
                                            {focusedNodeId && (<FocusBanner focusedNodeId={focusedNodeId} onExit={clearFocus} />)}
                                            <GraphLegend />
                                            <GraphSettings
                                                layoutMode={layoutMode}
                                                setLayoutMode={(v) => { setLayoutMode(v); try { localStorage.setItem('meshmon.layoutMode', v) } catch { } }}
                                                hideOnlineByDefault={hideOnlineByDefault}
                                                setHideOnlineByDefault={(v) => { setHideOnlineByDefault(v); try { localStorage.setItem('meshmon.hideOnlineByDefault', String(v)) } catch { } }}
                                                animationMode={animationMode}
                                                setAnimationMode={(v) => { setAnimationMode(v); try { localStorage.setItem('meshmon.animationMode', v) } catch { } }}
                                            />
                                        </div>
                                    </Panel>
                                    <Panel position="bottom-right" className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-2">
                                        <GraphStats
                                            totalNodes={Object.keys(networkData?.networks[selectedNetwork!]?.nodes || {}).length}
                                            onlineNodes={Object.values(networkData?.networks[selectedNetwork!]?.nodes || {}).filter((n: any) => n.status === 'online').length}
                                            connections={processedEdges.length}
                                            shownConnections={edges.filter(e => (typeof e.style?.opacity === 'number' ? e.style!.opacity! > 0.02 : true) || !!e.label).length}
                                        />
                                    </Panel>
                                </ReactFlow>
                            )}
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
