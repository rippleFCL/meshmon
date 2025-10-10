import { useTheme } from '../../contexts/ThemeContext'

interface Props {
    networkId: string
    nodeId: string
    status: 'online' | 'offline' | 'unknown'
    avgRtt: number
    inOnline: number
    inTotal: number
    outOnline: number
    outTotal: number
}

export default function NodeInfoRow({ networkId, nodeId, status, avgRtt, inOnline, inTotal, outOnline, outTotal }: Props) {
    const { isDark } = useTheme()
    return (
        <div className={`flex items-center space-x-3 p-3 rounded-lg transition-all duration-200 hover:shadow-sm ${isDark ? 'bg-gray-700' : 'bg-gray-50'}`}>
            <div className={`w-2 h-2 rounded-full transition-colors duration-200 ${status === 'online' ? 'bg-green-500' : (status === 'offline' ? 'bg-red-500' : 'bg-gray-400')}`}></div>
            <div className="flex-1">
                <p className={`text-sm font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>{nodeId} ({networkId})</p>
                <p className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                    {status} • Avg RTT: {avgRtt.toFixed(1)}ms
                </p>
            </div>
            <div className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                In: {inOnline}/{inTotal} • Out: {outOnline}/{outTotal}
            </div>
        </div>
    )
}
