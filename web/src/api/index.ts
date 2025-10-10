import axios from 'axios'
import { MeshMonApi } from '../types'
import { mockHealth } from './mockData'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// Feature flag to enable local mocks in dev
const USE_API_MOCKS = typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_USE_API_MOCKS === 'true'
const MOCK_DELAY_MS = 200

// Background snapshots for live data when using mocks
let liveViewDataSnapshot: MeshMonApi | null = null
let liveHealthSnapshot: any | null = null

export const getLiveViewDataSnapshot = (): MeshMonApi | null => liveViewDataSnapshot
export const getLiveHealthSnapshot = (): any | null => liveHealthSnapshot

// Main API - using the /view endpoint
export const meshmonApi = {
  getViewData: (): Promise<{ data: MeshMonApi }> => {
    if (USE_API_MOCKS) {
      // In mock mode, still prefer live API to reflect current graph, fallback to simple empty structure
      return api
        .get<MeshMonApi>('/view')
        .then((res) => {
          liveViewDataSnapshot = res.data as any
          return { data: res.data }
        })
        .catch(() => ({ data: { networks: {} } as MeshMonApi }))
    }
    return api.get<MeshMonApi>('/view').then((res) => ({ data: res.data }))
  },
}

// Health check
export const healthApi = {
  check: (): Promise<{ data: any }> => {
    if (USE_API_MOCKS) {
      // Fetch mock and live in parallel (return mock but keep live snapshot up to date)
      const mockPromise = new Promise<{ data: any }>((resolve) =>
        setTimeout(() => resolve({ data: mockHealth }), MOCK_DELAY_MS)
      )
      const livePromise = api
        .get('/health')
        .then((res) => {
          liveHealthSnapshot = res.data
          return res.data
        })
        .catch(() => null)

      return Promise.all([mockPromise, livePromise]).then(([mockRes]) => mockRes)
    }
    return api.get('/health')
  },
}

export default api
