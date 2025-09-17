import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { meshmonApi } from '../api'
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

    const statusColor = network.offline_nodes === 0 ? 'text-green-600 bg-green-100' :
        network.online_nodes > 0 ? 'text-yellow-600 bg-yellow-100' :
            'text-red-600 bg-red-100'

    const handleNetworkClick = () => {
        navigate(`/networks/${networkId}`)
    }

    return (
        <div
            className="card p-6 cursor-pointer hover:shadow-lg transition-shadow duration-200"
            onClick={handleNetworkClick}
        >
            <div className="flex items-center justify-between mb-4">
                <div>
                    <h3 className="text-lg font-medium text-gray-900">{networkId}</h3>
                    <p className="text-gray-600">Click to view detailed network information</p>
                </div>

                <div className="flex items-center space-x-4">
                    <span className={`px-3 py-1 text-sm font-medium rounded-full ${statusColor}`}>
                        {networkStatus}
                    </span>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                    <div className="text-2xl font-bold text-gray-900">{network.total_nodes}</div>
                    <div className="text-sm text-gray-600">Total Nodes</div>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                    <div className="text-2xl font-bold text-green-600">{network.online_nodes}</div>
                    <div className="text-sm text-gray-600">Online</div>
                </div>
                <div className="text-center p-4 bg-gray-50 rounded-lg">
                    <div className="text-2xl font-bold text-red-600">{network.offline_nodes}</div>
                    <div className="text-sm text-gray-600">Offline</div>
                </div>
            </div>
        </div>
    )
}

export default function Networks() {
    const [data, setData] = useState<MultiNetworkAnalysis | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const fetchData = async () => {
        try {
            setLoading(true)
            const response = await meshmonApi.getViewData()
            setData(response.data)
            setError(null)
        } catch (err) {
            setError('Failed to fetch network data')
            console.error('Error fetching data:', err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchData()
        const interval = setInterval(fetchData, 30000) // Refresh every 30 seconds
        return () => clearInterval(interval)
    }, [])

    if (loading) {
        return (
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Networks</h1>
                    <p className="text-gray-600">Monitor your mesh networks and node connections</p>
                </div>
                <div className="flex justify-center items-center h-64">
                    <div className="text-gray-600">Loading network data...</div>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900">Networks</h1>
                    <p className="text-gray-600">Monitor your mesh networks and node connections</p>
                </div>
                <div className="card p-6">
                    <div className="text-red-600 text-center">
                        <p>{error}</p>
                        <button
                            onClick={fetchData}
                            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
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
                    <h1 className="text-2xl font-bold text-gray-900">Networks</h1>
                    <p className="text-gray-600">Monitor your mesh networks and node connections</p>
                </div>
                <button
                    onClick={fetchData}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                    Refresh
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
