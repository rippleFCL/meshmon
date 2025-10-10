import type { LayoutEngine, LayoutOptions } from './types'
import type { Node, Edge } from 'reactflow'
import { estimateDiameterFromLabel } from '../utils'

const dense: LayoutEngine = {
  name: 'dense',
  compute(nodes: Node[], _edges: Edge[], _opts: LayoutOptions) {
    const maxDiam = Math.max(120, ...nodes.map(n => estimateDiameterFromLabel(n.data?.label)))
    const CELL = maxDiam + 72
    const total = nodes.length
    const cols = Math.max(1, Math.ceil(Math.sqrt(total)))
    const rows = Math.max(1, Math.ceil(total / cols))
    const gridW = cols * CELL
    const gridH = rows * CELL
    const pos = new Map<string, { x: number; y: number }>()
    nodes.forEach((n, index) => {
      const r = Math.floor(index / cols)
      const c = index % cols
      const x = (c + 0.5) * CELL - gridW / 2
      const y = (r + 0.5) * CELL - gridH / 2
      pos.set(n.id, { x, y })
    })
    return pos
  }
}

export default dense
