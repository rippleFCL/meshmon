import type { LayoutEngine, LayoutOptions } from './types'
import type { Node, Edge } from 'reactflow'
import { estimateDiameterFromLabel } from '../utils'

const concentric: LayoutEngine = {
  name: 'concentric',
  compute(nodes: Node[], _edges: Edge[], opts: LayoutOptions) {
    const mesh = nodes.filter(n => n.type === 'meshNode')
    const mons = nodes.filter(n => n.type === 'monitorNode')
    const nodeCount = mesh.length
    const monitorCount = mons.length
    const maxNodeDiam = Math.max(120, ...mesh.map(n => estimateDiameterFromLabel(n.data?.label)))
    const maxMonDiam = Math.max(120, ...mons.map(n => estimateDiameterFromLabel(n.data?.label)))
  const ui = Math.max(0, Math.min(100, opts.spacing ?? 48))
  const gamma = 3.0
  const t = Math.pow(ui / 100, gamma)
  const S = 16 + t * (400 - 16)
  const scale = S / 48
  const CHORD_MARGIN = 24 * scale
  const SEP_MARGIN = 80 * scale
  const nodeGap = maxNodeDiam + 60 * scale
  const monGap = maxMonDiam + 90 * scale
    const innerRChordMin = nodeCount > 1 ? (maxNodeDiam + CHORD_MARGIN) / (2 * Math.sin(Math.PI / nodeCount)) : 220
    const innerRArcMin = nodeCount > 0 ? (nodeCount * nodeGap) / (2 * Math.PI) : 220
  const innerMin = nodeCount > 0 ? Math.max(220 * scale, innerRChordMin, innerRArcMin) : 220 * scale
    const outerRChordMin = monitorCount > 1 ? (maxMonDiam + CHORD_MARGIN) / (2 * Math.sin(Math.PI / monitorCount)) : innerMin + 1
    const outerRArcMin = monitorCount > 0 ? (monitorCount * monGap) / (2 * Math.PI) : innerMin + 1
  const outerMin = monitorCount > 0 ? Math.max(outerRChordMin, outerRArcMin) : innerMin + 1
  const sepBase = (maxNodeDiam / 2) + (maxMonDiam / 2) + SEP_MARGIN
  const sep = sepBase * 1.15
    let C = Math.max(innerMin, outerMin - sep)
  const innerRadius = C
  const outerRadius = monitorCount > 0 ? C + sep : C + sep
    const pos = new Map<string, { x: number; y: number }>()
    mesh.forEach((n, index) => {
      const angle = (index / Math.max(1, nodeCount)) * 2 * Math.PI
      pos.set(n.id, { x: Math.cos(angle) * innerRadius, y: Math.sin(angle) * innerRadius })
    })
    mons.forEach((n, index) => {
      const angle = (index / Math.max(1, monitorCount)) * 2 * Math.PI
      pos.set(n.id, { x: Math.cos(angle) * outerRadius, y: Math.sin(angle) * outerRadius })
    })
    return pos
  }
}

export default concentric
