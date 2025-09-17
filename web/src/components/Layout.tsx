import { ReactNode } from 'react'
import Header from './Header'
import { useTheme } from '../contexts/ThemeContext'

interface LayoutProps {
    children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
    const { isDark } = useTheme()

    return (
        <div className={`min-h-screen ${isDark ? 'bg-gray-900' : 'bg-gray-50'}`}>
            <Header />
            <main className="pt-20 p-6">
                {children}
            </main>
        </div>
    )
}
