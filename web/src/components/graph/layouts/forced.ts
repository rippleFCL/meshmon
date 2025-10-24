import type { LayoutEngine, LayoutOptions } from './types'
import type { Node, Edge } from 'reactflow'
import { computeElkPositions } from '../elk'

const forced: LayoutEngine = {
  name: 'forced',
  async compute(nodes: Node[], edges: Edge[], opts: LayoutOptions) {
    return await computeElkPositions(nodes, edges, opts.spacing)
  }
}

export default forced
