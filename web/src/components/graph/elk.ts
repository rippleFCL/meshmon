import type { Node, Edge } from 'reactflow'
import { estimateDiameterFromLabel } from './utils'

export async function computeElkPositions(processedNodes: Node[], processedEdges: Edge[], spacing?: number) {
  const { default: ELK } = await import('elkjs/lib/elk.bundled.js')
  const elk = new ELK()
  const children = processedNodes.map(n => ({ id: n.id, width: estimateDiameterFromLabel(n.id), height: estimateDiameterFromLabel(n.id) }))
  const edges = processedEdges.map(e => ({ id: e.id, sources: [e.source], targets: [e.target] }))
  // spacing is 0..100 from UI; non-linear map to pixels ~1..240 for ELK
  const ui = Math.max(0, Math.min(100, spacing ?? 0))
  const gamma = 3.0 // even stronger ease-in curve
  const t = Math.pow(ui / 100, gamma)
  const s = 16 + t * (400 - 16)
  const pad = Math.max(0, Math.round(s / 6))
  const graph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'force',
      // Spacing controls
      'elk.spacing.nodeNode': String(s),
      'elk.spacing.edgeNode': String(Math.round(s * 0.9)),
      'elk.spacing.edgeEdge': String(Math.round(s * 0.8)),
      'elk.padding': String(pad),
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
