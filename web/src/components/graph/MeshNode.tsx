import { memo } from 'react'
import { useTheme } from '../../contexts/ThemeContext'
import { Handle, Position } from 'reactflow'

const DEBUG = false

const MeshNode = memo(({ data }: { data: any }) => {
    const { isDark } = useTheme()
    const isOnline = data.status === 'online'
    const baseSize = 120
    const labelLen = (data.label?.length ?? 0)
    const estWidth = Math.round(labelLen * 8.5 + 40)
    const nodeSize = Math.max(baseSize, Math.min(220, estWidth))
    const isHighlighted = data.isHighlighted
    const isDimmed = data.isDimmed
    const nodeOpacity = isDimmed ? 0.1 : isHighlighted ? 1 : 1
    const handleHover = data.onHover
    DEBUG && console.log(`Node ${data.label} - Online: ${isOnline}, Inbound: ${data.inboundCount}, Outbound: ${data.outboundCount}`)
    return (
        <div
            className={`relative flex flex-col items-center justify-center rounded-full border-2 shadow-none overflow-hidden ${isOnline ? (isDark ? 'bg-green-900/90 border-green-400 text-white' : 'bg-green-600 border-green-500 text-white') : (isDark ? 'bg-red-900/90 border-red-400 text-white' : 'bg-red-600 border-red-500 text-white')}`}
            style={{ width: `${nodeSize}px`, height: `${nodeSize}px`, opacity: nodeOpacity, willChange: 'transform, opacity', transition: 'opacity 220ms ease' }}
            onMouseEnter={() => handleHover && handleHover(data.nodeId || data.label)}
            onMouseLeave={() => handleHover && handleHover(null)}
        >
            <div className="text-sm font-bold truncate" title={data.label}>{data.label}</div>
            <div className="text-xs opacity-80 mt-0.5">Avg RTT: {Number.isFinite(data.avgRtt) ? `${(data.avgRtt as number).toFixed(1)}ms` : '—'}</div>
            <div className="flex items-center justify-center gap-4 text-xs opacity-80 mt-1">
                <span title="Online/Total inbound connections">↓{data.inboundOnlineCount}/{data.inboundCount}</span>
                <span title="Outbound connections">↑{data.outboundCount}</span>
            </div>
            <Handle type="source" id="s" position={Position.Right} isConnectable={false} style={{ width: 6, height: 6, opacity: 0, pointerEvents: 'none' }} />
            <Handle type="target" id="t" position={Position.Left} isConnectable={false} style={{ width: 6, height: 6, opacity: 0, pointerEvents: 'none' }} />
        </div>
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

export default MeshNode
