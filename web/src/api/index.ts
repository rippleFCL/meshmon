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

// Main API - using the /view endpoint
export const meshmonApi = {
  getViewData: (): Promise<{ data: MultiNetworkAnalysis }> => {
    if (USE_API_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve({ data: mockMultiNetworkAnalysis }), MOCK_DELAY_MS))
    }
    return api.get<MultiNetworkAnalysis>('/view')
  },
}

// Health check
export const healthApi = {
  check: (): Promise<{ data: any }> => {
    if (USE_API_MOCKS) {
      return new Promise((resolve) => setTimeout(() => resolve({ data: mockHealth }), MOCK_DELAY_MS))
    }
    return api.get('/health')
  },
}

export default api
