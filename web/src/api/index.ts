import axios from 'axios'
import { MultiNetworkAnalysis } from '../types'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// Main API - using the /view endpoint
export const meshmonApi = {
  getViewData: () => api.get<MultiNetworkAnalysis>('/view'),
}

// Health check
export const healthApi = {
  check: () => api.get('/health'),
}

export default api
