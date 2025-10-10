import ReactFlow, { Background, Controls, MiniMap } from 'reactflow'
import type { LayoutMode } from './layouts'
import type { Node, Edge } from 'reactflow'

type Props = {
    layoutMode: LayoutMode
    nodes: Node[]
    edges: Edge[]
    isDark: boolean
}

export default function LayoutedFlow({ layoutMode: _layoutMode, nodes, edges, isDark: _isDark }: Props) {
    return (
        <ReactFlow nodes={nodes} edges={edges} fitView>
            <Background />
            <MiniMap pannable zoomable />
            <Controls />
        </ReactFlow>
    )
}
