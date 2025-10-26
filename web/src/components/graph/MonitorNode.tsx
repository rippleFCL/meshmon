import { memo } from 'react'
import { useTheme } from '../../contexts/ThemeContext'
import { Handle, Position } from 'reactflow'
import { estimateDiameterFromLabel } from './utils'

const MonitorNode = memo(({ data }: { data: any }) => {
    const { isDark } = useTheme()
    const isOnline = data.status === 'online'
    const nodeSize = estimateDiameterFromLabel(data.label)
    const isHighlighted = data.isHighlighted
    const isDimmed = data.isDimmed
    const nodeOpacity = isDimmed ? 0.1 : isHighlighted ? 1 : 1
    const handleHover = data.onHover
    const group: string | undefined = data.group
    return (
        <div
            className={`relative flex flex-col items-center justify-center rounded-full border-2 shadow-none overflow-hidden ${isOnline ? (isDark ? 'bg-purple-900/90 border-purple-400 text-white' : 'bg-purple-600 border-purple-500 text-white') : (isDark ? 'bg-red-900/90 border-red-400 text-white' : 'bg-red-600 border-red-500 text-white')}`}
            style={{ width: `${nodeSize}px`, height: `${nodeSize}px`, opacity: nodeOpacity, willChange: 'transform, opacity', transition: 'opacity 220ms ease' }}
            onMouseEnter={() => handleHover && handleHover(data.nodeId || data.label)}
            onMouseLeave={() => handleHover && handleHover(null)}
            title={group ? `Group: ${group}` : undefined}
        >
            <div className="text-sm font-bold truncate" title={data.label}>{data.label}</div>
            <div className="text-xs opacity-80 mt-0.5">Avg RTT: {Number.isFinite(data.avgRtt) ? `${(data.avgRtt as number).toFixed(1)}ms` : '—'}</div>
            {group && (
                <div className="text-[11px] opacity-80 mt-0.5">{group}</div>
            )}
            <div className="flex justify-center text-xs opacity-80 mt-1">
                <span title="Nodes monitoring this monitor">←{data.inboundOnlineCount}/{data.inboundCount}</span>
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
        a.group === b.group
    )
})

export default MonitorNode
