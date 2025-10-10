import { BaseEdge, EdgeLabelRenderer, getBezierPath, useReactFlow } from 'reactflow'

export default function FloatingBezierEdge({ id, source, target, markerStart, markerEnd, style, label, labelStyle }: any) {
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

    const sCenter = { x: (sPos.x || 0), y: (sPos.y || 0) }
    const tCenter = { x: (tPos.x || 0), y: (tPos.y || 0) }

    const rsRaw = (sourceNode.data && sourceNode.data.nodeRadius) ? sourceNode.data.nodeRadius : Math.max(20, Math.min(sW, sH) / 2)
    const rtRaw = (targetNode.data && targetNode.data.nodeRadius) ? targetNode.data.nodeRadius : Math.max(20, Math.min(tW, tH) / 2)
    const strokeW = (style && (style as any).strokeWidth) ? Number((style as any).strokeWidth) : 2
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
    const targetX = tCenter.x - ux * (rt + markerOffset)
    const targetY = tCenter.y - uy * (rt + markerOffset)

    const horizontal = Math.abs(dx) >= Math.abs(dy)
    const sourcePosition = horizontal ? (dx >= 0 ? 'right' : 'left') : (dy >= 0 ? 'bottom' : 'top')
    const targetPosition = horizontal ? (dx >= 0 ? 'left' : 'right') : (dy >= 0 ? 'top' : 'bottom')

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
                        style={{ position: 'absolute', transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`, pointerEvents: 'all', ...(labelStyle || {}) }}
                        className="nodrag nopan"
                    >
                        {label}
                    </div>
                </EdgeLabelRenderer>
            )}
        </>
    )
}
