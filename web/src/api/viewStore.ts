import type { MeshMonApi } from '@/types'
import { meshmonApi } from '@/api'

export type ViewState = {
  data: MeshMonApi | null
  loading: boolean
  error: string | null
}

type Listener = (state: ViewState) => void

class ViewStore {
  private state: ViewState = { data: null, loading: true, error: null }
  private listeners = new Set<Listener>()
  private inFlight: Promise<void> | null = null
  private timer: number | null = null
  private refreshIntervals = new Map<Listener, number>()

  getState(): ViewState { return this.state }

  subscribe(listener: Listener, refreshMs = 10000): () => void {
    const first = this.listeners.size === 0
    this.listeners.add(listener)
    this.refreshIntervals.set(listener, refreshMs)
    queueMicrotask(() => listener(this.state))
    if (first) {
      this.refresh()
      this.startPolling()
    } else {
      this.updatePollingInterval()
    }
    return () => {
      this.listeners.delete(listener)
      this.refreshIntervals.delete(listener)
      if (this.listeners.size === 0) this.stopPolling()
      else this.updatePollingInterval()
    }
  }

  async refresh(): Promise<void> {
    if (this.inFlight) return this.inFlight
    this.setState({ ...this.state, loading: true, error: null })
    this.inFlight = (async () => {
      try {
        const res = await meshmonApi.getViewData()
        this.setState({ data: res.data, loading: false, error: null })
      } catch (e) {
        this.setState({ ...this.state, loading: false, error: 'Failed to fetch view data' })
      } finally {
        this.inFlight = null
      }
    })()
    return this.inFlight
  }

  private setState(next: ViewState) {
    this.state = next
    this.listeners.forEach(l => { try { l(this.state) } catch {} })
  }

  private startPolling() {
    this.stopPolling()
    const interval = this.currentInterval()
    if (interval <= 0) return
    this.timer = window.setInterval(() => { void this.refresh() }, interval)
  }
  private stopPolling() {
    if (this.timer !== null) { clearInterval(this.timer); this.timer = null }
  }
  private currentInterval(): number {
    if (this.refreshIntervals.size === 0) return 0
    let min = Infinity
    for (const v of this.refreshIntervals.values()) min = Math.min(min, v)
    return isFinite(min) ? min : 0
  }
  private updatePollingInterval() { this.startPolling() }
}

export const viewStore = new ViewStore()
