import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { meshmonApi } from '../api'
import { useRefresh } from '../contexts/RefreshContext'
import {
    MultiNetworkAnalysis,
    NetworkAnalysis
} from '../types'

interface NetworkCardProps {
    networkId: string
    network: NetworkAnalysis
}const NetworkCard: React.FC<NetworkCardProps> = ({ networkId, network }) => {
    const navigate = useNavigate()

    const networkStatus = network.offline_nodes === 0 ? 'Healthy' :
        network.online_nodes > 0 ? 'Degraded' : 'Offline'

    const statusColor = network.offline_nodes === 0 ? 'status-online' :
        network.online_nodes > 0 ? 'status-warning' :
            'status-offline'

    const handleNetworkClick = () => {
        navigate(`/networks/${networkId}`)
    }

    return (
        <div
            className="card p-6 cursor-pointer hover:shadow-lg dark:hover:shadow-gray-900/20 transition-all duration-200 data-fade"
            onClick={handleNetworkClick}
        >
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">{networkId}</h3>
                    <p className="text-gray-600 dark:text-gray-400">Click to view detailed network information</p>
                </div>

                <div className="flex items-center space-x-4">
                    <span className={`px-3 py-1 text-sm font-medium rounded-full ${statusColor}`}>
                        {networkStatus}
                    </span>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4 bg-gray-100 dark:bg-gray-700 rounded-lg">
                    <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{network.total_nodes}</div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">Total Nodes</div>
                </div>
                <div className="text-center p-4 bg-gray-100 dark:bg-gray-700 rounded-lg">
                    <div className="text-2xl font-bold text-green-600 dark:text-green-400">{network.online_nodes}</div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">Online</div>
                </div>
                <div className="text-center p-4 bg-gray-100 dark:bg-gray-700 rounded-lg">
                    <div className="text-2xl font-bold text-red-600 dark:text-red-400">{network.offline_nodes}</div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">Offline</div>
                </div>
            </div>
        </div>
    )
}

export default function Networks() {
    const { registerRefreshCallback } = useRefresh()
    const [data, setData] = useState<MultiNetworkAnalysis | null>(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchData = async (isInitialLoad = false) => {
        try {
            if (isInitialLoad) {
                setLoading(true)
            } else {
                setRefreshing(true)
            }

            const response = await meshmonApi.getViewData()
            setData(response.data)
            setError(null)
        } catch (err) {
            setError('Failed to fetch network data')
            console.error('Error fetching data:', err)
        } finally {
            if (isInitialLoad) {
                setLoading(false)
            } else {
                setRefreshing(false)
            }
        }
    }

    useEffect(() => {
        const fetchData = async (isInitialLoad = false) => {
            try {
                if (isInitialLoad) {
                    setLoading(true)
                } else {
                    setRefreshing(true)
                }

                const response = await meshmonApi.getViewData()
                setData(response.data)
                setError(null)
            } catch (err) {
                setError('Failed to fetch network data')
                console.error('Error fetching data:', err)
            } finally {
                if (isInitialLoad) {
                    setLoading(false)
                } else {
                    setRefreshing(false)
                }
            }
        }

        const handleRefresh = () => fetchData(false)

        fetchData(true) // Initial load
        const cleanup = registerRefreshCallback(handleRefresh) // Register refresh callback

        const interval = setInterval(() => fetchData(false), 10000) // Background refresh every 10 seconds

        return () => {
            clearInterval(interval)
            cleanup()
        }
    }, [registerRefreshCallback])

    if (loading) {
        return (
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Networks</h1>
                    <p className="text-gray-600 dark:text-gray-400">Monitor your mesh networks and node connections</p>
                </div>
                <div className="flex justify-center items-center h-64">
                    <div className="text-gray-600 dark:text-gray-400">Loading network data...</div>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Networks</h1>
                    <p className="text-gray-600 dark:text-gray-400">Monitor your mesh networks and node connections</p>
                </div>
                <div className="card p-6">
                    <div className="text-red-600 dark:text-red-400 text-center">
                        <p>{error}</p>
                        <button
                            onClick={() => fetchData(true)}
                            className="btn btn-primary mt-4"
                        >
                            Retry
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    if (!data || Object.keys(data.networks).length === 0) {
        return (
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Networks</h1>
                    <p className="text-gray-600">Monitor your mesh networks and node connections</p>
                </div>
                <div className="card p-6">
                    <div className="text-gray-600 text-center">No networks found</div>
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Networks</h1>
                    <p className="text-gray-600 dark:text-gray-400">Monitor your mesh networks and node connections</p>
                </div>
                {refreshing && (
                    <div className="flex items-center space-x-2 text-sm text-gray-600 dark:text-gray-400">
                        <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
                        <span>Updating...</span>
                    </div>
                )}
            </div>

            <div className="grid grid-cols-1 gap-6 data-fade">
                {Object.entries(data.networks).map(([networkId, network]) => (
                    <NetworkCard
                        key={networkId}
                        networkId={networkId}
                        network={network}
                    />
                ))}
            </div>
        </div>
    )
}
