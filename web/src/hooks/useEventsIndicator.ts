import { useEffect, useState } from 'react'
import { eventsApi } from '@/api/events'
import type { EventApi, ApiEventType } from '@/types/events'
import { useRefresh } from '@/contexts/RefreshContext'

export function useEventsIndicator(refreshMs = 10000) {
  const { registerRefreshCallback } = useRefresh()
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [severity, setSeverity] = useState<ApiEventType | null>(null)
  const [topTitles, setTopTitles] = useState<string[]>([])

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const res = await eventsApi.getEvents()
        if (!mounted) return
        const data: EventApi = res.data
        const events = Array.isArray(data?.events) ? data.events : []
        setCount(events.length)
        // Determine most severe: error > warning > info
        let sev: ApiEventType | null = null
        for (const ev of events) {
          if (ev.event_type === 'error') { sev = 'error'; break }
          if (ev.event_type === 'warning') { sev = sev ?? 'warning' }
          if (ev.event_type === 'info') { sev = sev ?? 'info' }
        }
        setSeverity(sev)
        // Top 3 titles by date desc
        const top = [...events]
          .sort((a, b) => (Date.parse(b.date) || 0) - (Date.parse(a.date) || 0))
          .slice(0, 3)
          .map(e => e.title)
        setTopTitles(top)
      } catch {
        if (!mounted) return
        setCount(0)
        setSeverity(null)
        setTopTitles([])
      } finally {
        if (mounted) setLoading(false)
      }
    }

    load()
    const cleanup = registerRefreshCallback(load)
    const interval = setInterval(load, refreshMs)
    return () => {
      mounted = false
      clearInterval(interval)
      cleanup()
    }
  }, [registerRefreshCallback, refreshMs])

  return { count, loading, severity, topTitles }
}
