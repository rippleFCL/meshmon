import type { EventApi, ApiEventType } from '@/types/events'
import { eventsApi } from '@/api/events'

export type EventsState = {
  data: EventApi | null
  loading: boolean
  error: string | null
  count: number
  severity: ApiEventType | null
  topTitles: string[]
}

type Listener = (state: EventsState) => void

// Singleton store to coalesce event polling across the app
class EventsStore {
  private state: EventsState = {
    data: null,
    loading: true,
    error: null,
    count: 0,
    severity: null,
    topTitles: [],
  }
  private listeners = new Set<Listener>()
  private inFlight: Promise<void> | null = null
  private timer: number | null = null
  private refreshIntervals = new Map<Listener, number>()

  getState(): EventsState {
    return this.state
  }

  subscribe(listener: Listener, refreshMs = 10000): () => void {
    const first = this.listeners.size === 0
    this.listeners.add(listener)
    this.refreshIntervals.set(listener, refreshMs)
    // Push current state immediately
    queueMicrotask(() => listener(this.state))

    if (first) {
      // Ensure we have fresh data and start polling
      this.refresh()
      this.startPolling()
    } else {
      // Recompute timer if a shorter interval is requested
      this.updatePollingInterval()
    }

    return () => {
      this.listeners.delete(listener)
      this.refreshIntervals.delete(listener)
      if (this.listeners.size === 0) {
        this.stopPolling()
      } else {
        this.updatePollingInterval()
      }
    }
  }

  async refresh(): Promise<void> {
    if (this.inFlight) return this.inFlight
    this.setState({ ...this.state, loading: true, error: null })
    this.inFlight = (async () => {
      try {
        const res = await eventsApi.getEvents()
        const data = res.data
        const events = Array.isArray(data?.events) ? data.events : []
        const { count, severity, topTitles } = this.computeDerived(events)
        this.setState({ data, loading: false, error: null, count, severity, topTitles })
      } catch (e) {
        this.setState({ ...this.state, loading: false, error: 'Failed to fetch events', count: 0, severity: null, topTitles: [] })
      } finally {
        this.inFlight = null
      }
    })()
    return this.inFlight
  }

  private computeDerived(events: EventApi['events']) {
    // Determine most severe: error > warning > info
    let sev: ApiEventType | null = null
    for (const ev of events) {
      if (ev.event_type === 'error') { sev = 'error'; break }
      if (ev.event_type === 'warning') { sev = sev ?? 'warning' }
      if (ev.event_type === 'info') { sev = sev ?? 'info' }
    }
    const topTitles = [...events]
      .sort((a, b) => (Date.parse(b.date) || 0) - (Date.parse(a.date) || 0))
      .slice(0, 3)
      .map(e => e.title)
    return { count: events.length, severity: sev, topTitles }
  }

  private setState(next: EventsState) {
    this.state = next
    this.listeners.forEach(l => {
      try { l(this.state) } catch (e) { /* no-op */ }
    })
  }

  private startPolling() {
    this.stopPolling()
    const interval = this.currentInterval()
    if (interval <= 0) return
    this.timer = window.setInterval(() => {
      void this.refresh()
    }, interval)
  }

  private stopPolling() {
    if (this.timer !== null) {
      clearInterval(this.timer)
      this.timer = null
    }
  }

  private currentInterval(): number {
    if (this.refreshIntervals.size === 0) return 0
    let min = Infinity
    for (const v of this.refreshIntervals.values()) min = Math.min(min, v)
    return isFinite(min) ? min : 0
  }

  private updatePollingInterval() {
    const next = this.currentInterval()
    if (next === 0) {
      this.stopPolling()
    } else {
      this.startPolling()
    }
  }
}

export const eventsStore = new EventsStore()
