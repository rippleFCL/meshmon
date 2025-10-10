import axios from 'axios'
import { MeshMonApi } from '../types'
import { mockHealth, mockMeshMonApi } from './mockData'

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
      // Return deterministic mock data immediately for a smooth dev experience
      const mock = new Promise<{ data: MeshMonApi }>((resolve) => setTimeout(() => resolve({ data: mockMeshMonApi }), MOCK_DELAY_MS))
      // Also try to fetch live data in the background to keep a snapshot for debugging
      api
        .get<MeshMonApi>('/view')
        .then((res) => { liveViewDataSnapshot = res.data as any })
        .catch(() => { /* ignore in mock mode */ })
      return mock
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
