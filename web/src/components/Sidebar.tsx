import { Link } from 'react-router-dom'
import {
    LayoutDashboard,
    Network
} from 'lucide-react'

interface SidebarProps {
    currentPath: string
}

const navigation = [
    { name: 'Dashboard', href: '/', icon: LayoutDashboard },
    { name: 'Networks', href: '/networks', icon: Network },
]

export default function Sidebar({ currentPath }: SidebarProps) {
    return (
        <div className="fixed inset-y-0 left-0 z-50 w-64 bg-white shadow-lg">
            <div className="flex flex-col h-full">
                <nav className="flex-1 px-4 py-6 space-y-2">
                    {navigation.map((item) => {
                        const isActive = currentPath === item.href || (currentPath === '/' && item.href === '/dashboard')
                        return (
                            <Link
                                key={item.name}
                                to={item.href}
                                className={`
                  flex items-center px-3 py-2 rounded-md text-sm font-medium transition-colors duration-200
                  ${isActive
                                        ? 'bg-primary-100 text-primary-700 border-r-2 border-primary-500'
                                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                                    }
                `}
                            >
                                <item.icon className={`mr-3 h-5 w-5 ${isActive ? 'text-primary-500' : 'text-gray-400'}`} />
                                {item.name}
                            </Link>
                        )
                    })}
                </nav>
            </div>
        </div>
    )
}
