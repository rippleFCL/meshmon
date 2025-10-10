import type { Node, Edge } from 'reactflow'

export type LayoutMode = 'forced' | 'concentric' | 'dense' | 'pretty'

export interface LayoutOptions {
  isDark: boolean
}

export interface LayoutEngine {
  name: LayoutMode
  compute(nodes: Node[], edges: Edge[], opts: LayoutOptions): Promise<Map<string, { x: number; y: number }>> | Map<string, { x: number; y: number }>
}
