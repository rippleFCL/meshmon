import axios from 'axios'
import { MultiNetworkAnalysis } from '../types'
import { mockHealth, mockMultiNetworkAnalysis } from './mockData'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// Feature flag to enable local mocks in dev
const USE_API_MOCKS = typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_USE_API_MOCKS === 'true'
const MOCK_DELAY_MS = 200

// Background snapshots for live data when using mocks
let liveViewDataSnapshot: MultiNetworkAnalysis | null = null
let liveHealthSnapshot: any | null = null

export const getLiveViewDataSnapshot = (): MultiNetworkAnalysis | null => liveViewDataSnapshot
export const getLiveHealthSnapshot = (): any | null => liveHealthSnapshot

// Main API - using the /view endpoint
export const meshmonApi = {
  getViewData: (): Promise<{ data: MultiNetworkAnalysis }> => {
    if (USE_API_MOCKS) {
      // Fetch mock and live in parallel and merge networks (live overwrites on id collision)
      const mockPromise = new Promise<{ data: MultiNetworkAnalysis }>((resolve) =>
        setTimeout(() => resolve({ data: mockMultiNetworkAnalysis }), MOCK_DELAY_MS)
      )
      const livePromise = api
        .get<MultiNetworkAnalysis>('/view')
        .then((res) => {
          liveViewDataSnapshot = res.data
          return res.data
        })
        .catch(() => null)

      return Promise.all([mockPromise, livePromise]).then(([mockRes, liveData]) => {
        const merged: MultiNetworkAnalysis = {
          networks: {
            ...mockRes.data.networks,
            ...(liveData?.networks || {}),
          },
        }
        return { data: merged }
      })
    }
    return api.get<MultiNetworkAnalysis>('/view')
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
