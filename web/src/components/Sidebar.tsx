import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { RefreshCw, Wifi, WifiOff, Sun, Moon, LayoutDashboard, GitBranch, Bell, Database, ChevronLeft, ChevronRight } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import { useRefresh } from '../contexts/RefreshContext'
import { useEventsIndicator } from '@/hooks/useEventsIndicator'

const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Network Graph', href: '/graph', icon: GitBranch },
    { name: 'Notification Clusters', href: '/notification-cluster', icon: Bell },
    { name: 'Cluster', href: '/cluster', icon: Database },
    { name: 'Events', href: '/events', icon: Bell },
]

export default function Sidebar() {
    const [isConnected] = useState(true)
    const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
        try {
            const v = localStorage.getItem('meshmon.sidebarCollapsed')
            return v === 'true'
        } catch {
            return false
        }
    })

    useEffect(() => {
        try {
            localStorage.setItem('meshmon.sidebarCollapsed', String(isCollapsed))
        } catch { }
    }, [isCollapsed])
    const { isDark, toggleTheme } = useTheme()
    const { triggerRefresh, isRefreshing } = useRefresh()
    const { count: eventsCount, severity: eventsSeverity } = useEventsIndicator(10000)
    const location = useLocation()

    const handleRefresh = () => {
        triggerRefresh()
    }

    return (
        <aside className={`hidden md:flex ${isCollapsed ? 'w-16' : 'w-64'} shrink-0 ${isDark ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-r min-h-screen flex-col overflow-hidden`}>
            <div className="px-3 py-4 border-b dark:border-gray-700 border-gray-200">
                <div className={`flex items-center ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
                    <div className={`flex items-center ${isCollapsed ? 'justify-center' : 'space-x-2'}`}>
                        <Wifi className="h-6 w-6 text-primary-600" />
                        {!isCollapsed && (<h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">MeshMon</h1>)}
                    </div>
                    {!isCollapsed && (
                        <button
                            onClick={() => setIsCollapsed(true)}
                            className="p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
                            title="Collapse sidebar"
                        >
                            <ChevronLeft className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                        </button>
                    )}
                    {isCollapsed && (
                        <button
                            onClick={() => setIsCollapsed(false)}
                            className="p-1 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700"
                            title="Expand sidebar"
                        >
                            <ChevronRight className="h-4 w-4 text-gray-600 dark:text-gray-300" />
                        </button>
                    )}
                </div>
            </div>

            <nav className="flex-1 overflow-y-auto p-2 space-y-1">
                {navigation.map((item) => {
                    const isActive = location.pathname === item.href
                    return (
                        <Link
                            key={item.name}
                            to={item.href}
                            title={item.name}
                            className={`
                flex items-center ${isCollapsed ? 'justify-center' : ''} px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200
                ${isActive
                                    ? isDark
                                        ? 'bg-blue-900 text-blue-300'
                                        : 'bg-primary-100 text-primary-700'
                                    : isDark
                                        ? 'text-gray-300 hover:bg-gray-700 hover:text-white'
                                        : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                                }
              `}
                        >
                            <item.icon className={`${isCollapsed ? '' : 'mr-2'} h-4 w-4 ${isActive
                                ? isDark ? 'text-blue-400' : 'text-primary-500'
                                : isDark ? 'text-gray-400' : 'text-gray-400'
                                }`} />
                            {!isCollapsed && (
                                <span className="truncate flex items-center gap-2">
                                    {item.name}
                                    {item.name === 'Events' && eventsCount > 0 && (
                                        <span
                                            className={`text-[10px] px-1.5 py-0.5 rounded-full ${eventsSeverity === 'error'
                                                    ? (isDark ? 'bg-red-800 text-red-200' : 'bg-red-100 text-red-700')
                                                    : eventsSeverity === 'warning'
                                                        ? (isDark ? 'bg-yellow-800 text-yellow-200' : 'bg-yellow-100 text-yellow-700')
                                                        : (isDark ? 'bg-blue-800 text-blue-200' : 'bg-blue-100 text-blue-700')
                                                }`}
                                        >
                                            {eventsCount}
                                        </span>
                                    )}
                                </span>
                            )}
                        </Link>
                    )
                })}
            </nav>

            <div className="p-2 border-t dark:border-gray-700 border-gray-200 space-y-3">
                <div className={`flex ${isCollapsed ? 'flex-col items-center gap-2' : 'items-center justify-between'}`}>
                    <button
                        onClick={toggleTheme}
                        className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors duration-200"
                        title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                    >
                        {isDark ? (
                            <Sun className="h-5 w-5 text-gray-300" />
                        ) : (
                            <Moon className="h-5 w-5 text-gray-600" />
                        )}
                    </button>

                    {isCollapsed ? (
                        <button
                            onClick={handleRefresh}
                            disabled={isRefreshing}
                            className="p-2 rounded-lg border border-gray-200 dark:border-gray-600 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50"
                            title={isRefreshing ? 'Refreshing…' : 'Refresh'}
                        >
                            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                        </button>
                    ) : (
                        <button
                            onClick={handleRefresh}
                            disabled={isRefreshing}
                            className="btn btn-secondary flex items-center space-x-2 disabled:opacity-50"
                        >
                            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                            <span className="text-sm">{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
                        </button>
                    )}
                </div>

                <div className={`flex items-center ${isCollapsed ? 'justify-center mt-1' : 'space-x-2'}`}>
                    {isConnected ? (
                        <>
                            <Wifi className="h-4 w-4 text-green-500" />
                            {!isCollapsed && <span className="text-sm text-green-600 dark:text-green-400 font-medium">Connected</span>}
                        </>
                    ) : (
                        <>
                            <WifiOff className="h-4 w-4 text-red-500" />
                            {!isCollapsed && <span className="text-sm text-red-600 dark:text-red-400 font-medium">Disconnected</span>}
                        </>
                    )}
                </div>
            </div>
        </aside>
    )
}
