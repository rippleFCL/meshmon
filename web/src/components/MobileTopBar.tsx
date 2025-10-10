import { Link, useLocation } from 'react-router-dom'
import { LayoutDashboard, GitBranch, Bell, Database, RefreshCw, Wifi, WifiOff, Sun, Moon } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import { useRefresh } from '../contexts/RefreshContext'
import { useState } from 'react'

const nav = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Graph', href: '/graph', icon: GitBranch },
    { name: 'Notifications', href: '/notification-cluster', icon: Bell },
    { name: 'Cluster', href: '/cluster', icon: Database },
]

export default function MobileTopBar() {
    const { isDark, toggleTheme } = useTheme()
    const { triggerRefresh, isRefreshing } = useRefresh()
    const [isConnected] = useState(true)
    const location = useLocation()

    return (
        <div className={`${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-b`}>
            <div className="px-3 py-2 flex items-center justify-between">
                <div className="flex items-center space-x-2">
                    <span className={`font-bold ${isDark ? 'text-gray-100' : 'text-gray-900'}`}>MeshMon</span>
                    {isConnected ? <Wifi className="h-4 w-4 text-green-500" /> : <WifiOff className="h-4 w-4 text-red-500" />}
                </div>
                <div className="flex items-center space-x-2">
                    <button onClick={toggleTheme} className="p-2 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700">
                        {isDark ? <Sun className="h-5 w-5 text-gray-300" /> : <Moon className="h-5 w-5 text-gray-600" />}
                    </button>
                    <button onClick={() => triggerRefresh()} disabled={isRefreshing} className="btn btn-secondary flex items-center space-x-1 disabled:opacity-50">
                        <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                        <span className="text-sm">{isRefreshing ? 'Refreshing…' : 'Refresh'}</span>
                    </button>
                </div>
            </div>
            <div className="flex items-center overflow-x-auto no-scrollbar divide-x dark:divide-gray-700 divide-gray-200">
                {nav.map(item => {
                    const active = location.pathname === item.href
                    return (
                        <Link
                            key={item.name}
                            to={item.href}
                            className={`flex-1 min-w-0 px-3 py-2 flex items-center justify-center text-sm ${active ? (isDark ? 'bg-blue-900 text-blue-300' : 'bg-primary-100 text-primary-700') : (isDark ? 'text-gray-300' : 'text-gray-700')}`}
                        >
                            <item.icon className="h-4 w-4 mr-1" />
                            <span className="truncate">{item.name}</span>
                        </Link>
                    )
                })}
            </div>
        </div>
    )
}
