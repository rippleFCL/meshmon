import type { LayoutEngine, LayoutMode } from './types'
import forced from './forced'
import concentric from './concentric'
import dense from './dense'
import pretty from './pretty'

const registry: Record<LayoutMode, LayoutEngine> = {
  forced,
  concentric,
  dense,
  pretty,
}

export function getLayoutEngine(name: LayoutMode): LayoutEngine {
  return registry[name]
}

export type { LayoutMode, LayoutOptions, LayoutEngine } from './types'
