import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import MobileTopBar from '@/components/MobileTopBar'
import { useTheme } from '../contexts/ThemeContext'

interface LayoutProps {
    children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
    const { isDark } = useTheme()

    return (
        <div className={`min-h-screen ${isDark ? 'bg-gray-900' : 'bg-gray-50'}`}>
            {/* Mobile navbar */}
            <div className="md:hidden sticky top-0 z-20">
                <MobileTopBar />
            </div>
            <div className="flex">
                <Sidebar />
                <main className="flex-1 p-4 md:p-6 min-w-0">
                    {children}
                </main>
            </div>
        </div>
    )
}
