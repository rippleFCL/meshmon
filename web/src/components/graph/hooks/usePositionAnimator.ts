import { useCallback, useRef } from 'react'
import type { Node } from 'reactflow'

export function usePositionAnimator(setNodes: (updater: (curr: Node[]) => Node[]) => void) {
  const nodesRef = useRef<Node[]>([])
  const posAnimIdRef = useRef<number>(0)
  const posAnimFrameRef = useRef<number | null>(null)

  const setNodesRef = (nodes: Node[]) => { nodesRef.current = nodes }

  const cancelPositionAnimation = useCallback(() => {
    posAnimIdRef.current++
    if (posAnimFrameRef.current != null) {
      cancelAnimationFrame(posAnimFrameRef.current)
      posAnimFrameRef.current = null
    }
  }, [])

  const animateNodePositions = useCallback((targetPos: Map<string, { x: number; y: number }>, durationMs = 450) => {
    cancelPositionAnimation()
    const startId = ++posAnimIdRef.current
    const startTime = performance.now()
    const startPos = new Map<string, { x: number; y: number }>(
      (nodesRef.current || []).map((n) => [n.id, { x: n.position.x, y: n.position.y }])
    )
    const step = (now: number) => {
      if (startId !== posAnimIdRef.current) return
      const t = Math.min(1, (now - startTime) / durationMs)
      const ease = (u: number) => 1 - Math.pow(1 - u, 3)
      const k = ease(t)
      setNodes((curr) => curr.map((n) => {
        const s = startPos.get(n.id) || n.position
        const tgt = targetPos.get(n.id) || n.position
        const x = s.x + (tgt.x - s.x) * k
        const y = s.y + (tgt.y - s.y) * k
        return { ...n, position: { x, y } }
      }))
      if (t < 1) {
        posAnimFrameRef.current = requestAnimationFrame(step)
      } else {
        posAnimFrameRef.current = null
      }
    }
    posAnimFrameRef.current = requestAnimationFrame(step)
  }, [cancelPositionAnimation, setNodes])

  return { setNodesRef, animateNodePositions, cancelPositionAnimation }
}
