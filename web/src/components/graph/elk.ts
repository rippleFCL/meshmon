import type { Node, Edge } from 'reactflow'
import { estimateDiameterFromLabel } from './utils'

export async function computeElkPositions(processedNodes: Node[], processedEdges: Edge[]) {
  const { default: ELK } = await import('elkjs/lib/elk.bundled.js')
  const elk = new ELK()
  const children = processedNodes.map(n => ({ id: n.id, width: estimateDiameterFromLabel(n.id), height: estimateDiameterFromLabel(n.id) }))
  const edges = processedEdges.map(e => ({ id: e.id, sources: [e.source], targets: [e.target] }))
  const graph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'force',
      // Tweak spacing for readability
      'elk.spacing.nodeNode': '90',
      'elk.spacing.edgeNode': '90',
      'elk.spacing.edgeEdge': '90',
      // Force layout specific tweaks (kept conservative for stability)
      'elk.quality': 'default',
      'elk.force.iterations': '600',
    },
    children,
    edges,
  }
  const res = await elk.layout(graph as any)
  const laidChildren = (res.children || []) as Array<{ id: string, x: number, y: number, width: number, height: number }>
  const centers = laidChildren.map(c => ({ id: c.id, cx: c.x + c.width / 2, cy: c.y + c.height / 2 }))
  const minX = Math.min(...centers.map(c => c.cx))
  const maxX = Math.max(...centers.map(c => c.cx))
  const minY = Math.min(...centers.map(c => c.cy))
  const maxY = Math.max(...centers.map(c => c.cy))
  const normCx = (minX + maxX) / 2
  const normCy = (minY + maxY) / 2
  return new Map<string, { x: number; y: number }>(centers.map(c => [c.id, { x: c.cx - normCx, y: c.cy - normCy }]))
}
