import { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

interface LayoutProps {
    children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
    const location = useLocation()

    return (
        <div className="min-h-screen bg-gray-50">
            <Header />
            <div className="flex pt-20">
                <Sidebar currentPath={location.pathname} />
                <main className="flex-1 ml-64 p-6">
                    {children}
                </main>
            </div>
        </div>
    )
}
