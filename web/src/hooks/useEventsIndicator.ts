import { useEffect, useState } from 'react'
import type { ApiEventType } from '@/types/events'
import { useRefresh } from '@/contexts/RefreshContext'
import { eventsStore } from '@/api/eventsStore'

export function useEventsIndicator(refreshMs = 10000) {
  const { registerRefreshCallback } = useRefresh()
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [severity, setSeverity] = useState<ApiEventType | null>(null)
  const [topTitles, setTopTitles] = useState<string[]>([])

  useEffect(() => {
    const unsub = eventsStore.subscribe((s) => {
      setCount(s.count)
      setLoading(s.loading)
      setSeverity(s.severity)
      setTopTitles(s.topTitles)
    }, refreshMs)
    const cleanup = registerRefreshCallback(() => { void eventsStore.refresh() })
    return () => { unsub(); cleanup() }
  }, [registerRefreshCallback, refreshMs])

  return { count, loading, severity, topTitles }
}
