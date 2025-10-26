import type { Node, Edge } from 'reactflow'
import { estimateDiameterFromLabel } from './utils'

export async function computeElkPositions(processedNodes: Node[], processedEdges: Edge[], spacing?: number, advanced?: { forced?: { elkQuality?: 'default' | 'proof', iterations?: number, minEdgeLength?: number, aspectRatio?: number } }) {
  const { default: ELK } = await import('elkjs/lib/elk.bundled.js')
  const elk = new ELK()
  // Size nodes based on their rendered label (fallback to id), and clamp to sane bounds to avoid wild forces
  const children = processedNodes.map(n => {
    const label = (n.data as any)?.label || n.id
    const d = estimateDiameterFromLabel(label)
    const size = Math.max(36, Math.min(140, Math.round(d)))
    return { id: n.id, width: size, height: size }
  })
  const edges = processedEdges.map(e => ({ id: e.id, sources: [e.source], targets: [e.target] }))
  // spacing is 0..100 from UI; non-linear map to a tighter, more useful pixel range for ELK
  const ui = Math.max(0, Math.min(100, spacing ?? 0))
  const gamma = 3.0 // ease-in for fine control near zero
  const t = Math.pow(ui / 100, gamma)
  const s = 14 + t * (300 - 14) // 14..300 px base spacing
  const pad = Math.max(6, Math.round(s / 8))
  const graph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'force',
      // Spacing controls
      'elk.spacing.nodeNode': String(Math.round(s)),
      'elk.spacing.edgeNode': String(Math.round(s * 0.85)),
      'elk.spacing.edgeEdge': String(Math.round(s * 0.75)),
      'elk.spacing.componentComponent': String(Math.round(s * 1.1)),
      'elk.padding': String(pad),
      // Force layout quality and stability
      'elk.quality': String(advanced?.forced?.elkQuality || 'proof'),
      'elk.force.iterations': String(advanced?.forced?.iterations || 1200),
      // Prefer stable, reproducible layouts across refreshes
      'elk.randomSeed': '42',
      // Encourage a slightly wider spread for readability
      'elk.aspectRatio': String(advanced?.forced?.aspectRatio || 1.2),
      // Encourage a minimum edge length if requested
      ...(advanced?.forced?.minEdgeLength ? { 'elk.minimalNodeNodeDistance': String(advanced.forced.minEdgeLength) } : {}),
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
