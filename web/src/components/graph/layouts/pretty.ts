import type { LayoutEngine, LayoutOptions } from './types'
import type { Node, Edge } from 'reactflow'
import { estimateDiameterFromLabel } from '../utils'

const pretty: LayoutEngine = {
  name: 'pretty',
  compute(nodes: Node[], _edges: Edge[], _opts: LayoutOptions) {
    const golden = Math.PI * (3 - Math.sqrt(5))
    const maxDiam = Math.max(120, ...nodes.map(n => estimateDiameterFromLabel(n.data?.label)))
    const R = Math.max(60, Math.round(maxDiam / 2))
    const MARGIN = 48
    const c = (R * 2 + MARGIN) / Math.sqrt(Math.PI)
    const pos = new Map<string, { x: number; y: number }>()
    nodes.forEach((n, index) => {
      const angle = index * golden
      const r = c * Math.sqrt(index + 1)
      const x = Math.cos(angle) * r
      const y = Math.sin(angle) * r
      pos.set(n.id, { x, y })
    })
    return pos
  }
}

export default pretty
