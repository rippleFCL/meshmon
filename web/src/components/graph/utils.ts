// Estimate a node diameter from its label length to pre-allocate space/layout
export const estimateDiameterFromLabel = (label?: string) => {
  const baseSize = 120
  const len = (label?.length ?? 0)
  const estWidth = Math.round(len * 8.5 + 40)
  return Math.max(baseSize, Math.min(220, estWidth))
}

export const isAdjacentByDistance = (a: { x: number, y: number }, b: { x: number, y: number }, threshold = 350) => {
  const dx = b.x - a.x
  const dy = b.y - a.y
  return Math.hypot(dx, dy) < threshold
}
