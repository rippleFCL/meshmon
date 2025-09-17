import { useState } from 'react'
import { RefreshCw, Wifi, WifiOff } from 'lucide-react'

export default function Header() {
    const [isConnected] = useState(true)

    const handleRefresh = () => {
        window.location.reload()
    }

    return (
        <header className="bg-white shadow-sm border-b border-gray-200 fixed top-0 left-0 right-0 z-10">
            <div className="px-6 py-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                        <div className="flex items-center space-x-2">
                            <Wifi className="h-6 w-6 text-primary-600" />
                            <h1 className="text-xl font-bold text-gray-900">MeshMon</h1>
                        </div>
                    </div>

                    <div className="flex items-center space-x-4">
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
                                    <span className="text-sm text-green-600 font-medium">Connected</span>
                                </>
                            ) : (
                                <>
                                    <WifiOff className="h-4 w-4 text-red-500" />
                                    <span className="text-sm text-red-600 font-medium">Disconnected</span>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </header>
    )
}
