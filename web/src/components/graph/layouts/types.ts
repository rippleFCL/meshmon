import type { Node, Edge } from 'reactflow'

export type LayoutMode = 'forced' | 'concentric' | 'dense' | 'pretty'

export interface LayoutOptions {
  isDark: boolean
  // Overall spacing factor in pixels (baseline ~48). Layouts should scale margins/gaps with this.
  spacing: number
  // Optional advanced options for specific layouts (e.g., forced/ELK)
  // Layout engines should ignore keys they don't use.
  advanced?: any
}

export interface LayoutEngine {
  name: LayoutMode
  compute(nodes: Node[], edges: Edge[], opts: LayoutOptions): Promise<Map<string, { x: number; y: number }>> | Map<string, { x: number; y: number }>
}
