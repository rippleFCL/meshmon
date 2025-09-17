import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { RefreshCw, Wifi, WifiOff, Sun, Moon, LayoutDashboard, Network } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'

const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Networks', href: '/networks', icon: Network },
]

export default function Header() {
    const [isConnected] = useState(true)
    const { isDark, toggleTheme } = useTheme()
    const location = useLocation()

    const handleRefresh = () => {
        window.location.reload()
    }

    return (
        <header className="bg-white dark:bg-gray-800 shadow-sm border-b border-gray-200 dark:border-gray-700 fixed top-0 left-0 right-0 z-10 transition-colors duration-200">
            <div className="px-6 py-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-8">
                        <div className="flex items-center space-x-2">
                            <Wifi className="h-6 w-6 text-primary-600" />
                            <h1 className="text-xl font-bold text-gray-900 dark:text-gray-100">MeshMon</h1>
                        </div>

                        <nav className="flex space-x-1">
                            {navigation.map((item) => {
                                const isActive = location.pathname === item.href
                                return (
                                    <Link
                                        key={item.name}
                                        to={item.href}
                                        className={`
                                            flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200
                                            ${isActive
                                                ? isDark
                                                    ? 'bg-blue-900 text-blue-300'
                                                    : 'bg-primary-100 text-primary-700'
                                                : isDark
                                                    ? 'text-gray-300 hover:bg-gray-700 hover:text-white'
                                                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                                            }
                                        `}
                                    >
                                        <item.icon className={`mr-2 h-4 w-4 ${isActive
                                            ? isDark ? 'text-blue-400' : 'text-primary-500'
                                            : isDark ? 'text-gray-400' : 'text-gray-400'
                                            }`} />
                                        {item.name}
                                    </Link>
                                )
                            })}
                        </nav>
                    </div>

                    <div className="flex items-center space-x-4">
                        <button
                            onClick={toggleTheme}
                            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors duration-200"
                            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
                        >
                            {isDark ? (
                                <Sun className="h-5 w-5 text-gray-600 dark:text-gray-300" />
                            ) : (
                                <Moon className="h-5 w-5 text-gray-600 dark:text-gray-300" />
                            )}
                        </button>

                        <button
                            onClick={handleRefresh}
                            className="btn btn-secondary flex items-center space-x-2"
                        >
                            <RefreshCw className="h-4 w-4" />
                            <span>Refresh</span>
                        </button>

                        <div className="flex items-center space-x-2">
                            {isConnected ? (
                                <>
                                    <Wifi className="h-4 w-4 text-green-500" />
                                    <span className="text-sm text-green-600 dark:text-green-400 font-medium">Connected</span>
                                </>
                            ) : (
                                <>
                                    <WifiOff className="h-4 w-4 text-red-500" />
                                    <span className="text-sm text-red-600 dark:text-red-400 font-medium">Disconnected</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </header>
    )
}
