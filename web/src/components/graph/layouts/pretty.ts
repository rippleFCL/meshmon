import type { LayoutEngine, LayoutOptions } from './types'
import type { Node, Edge } from 'reactflow'
import { estimateDiameterFromLabel } from '../utils'

const pretty: LayoutEngine = {
  name: 'pretty',
  compute(nodes: Node[], _edges: Edge[], opts: LayoutOptions) {
    const golden = Math.PI * (3 - Math.sqrt(5))
    const maxDiam = Math.max(120, ...nodes.map(n => estimateDiameterFromLabel(n.data?.label)))
  const ui = Math.max(0, Math.min(100, opts.spacing ?? 48))
  const gamma = 3.0
  const t = Math.pow(ui / 100, gamma)
  const S = 16 + t * (400 - 16)
  const scale = S / 48
    const R = Math.max(60, Math.round(maxDiam / 2))
    const MARGIN = 48 * scale
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
