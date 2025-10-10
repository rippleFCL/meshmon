import { useNavigate } from 'react-router-dom'
import { useTheme } from '../../contexts/ThemeContext'
import { NetworkInfoNew } from '../../types'

interface Props {
    networkId: string
    network: NetworkInfoNew
}

export default function NetworkItem({ networkId, network }: Props) {
    const { isDark } = useTheme()
    const navigate = useNavigate()
    const nodeEntries = Object.values(network.nodes)
    const total = nodeEntries.length
    const online = nodeEntries.filter(n => n.status === 'online').length
    const offline = nodeEntries.filter(n => n.status === 'offline').length
    const status = offline === 0 && online === total && total > 0 ? 'online' : online > 0 ? 'warning' : 'offline'
    const statusClass = status === 'online' ? 'status-online' : status === 'offline' ? 'status-offline' : 'status-warning'

    return (
        <div
            className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all duration-200 min-w-64 flex-1 ${isDark ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-50 hover:bg-gray-100'} hover:shadow-md`}
            onClick={() => navigate(`/networks/${networkId}`)}
        >
            <div>
                <span className={`font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>{networkId}</span>
                <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'} mt-1`}>
                    {online}/{total} nodes online
                </p>
            </div>
            <span className={`px-3 py-1 text-xs font-medium rounded-full ${statusClass}`}>
                {status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
        </div>
    )
}
