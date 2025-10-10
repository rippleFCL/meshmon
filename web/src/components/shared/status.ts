export type UiStatus = 'online' | 'offline' | 'degraded' | 'unknown'

export const getStatusColor = (status: string) => {
    switch (status) {
        case 'online':
            return 'status-online'
        case 'offline':
            return 'status-offline'
        case 'degraded':
            return 'status-warning'
        case 'unknown':
        default:
            return 'text-gray-600 dark:text-gray-400 bg-gray-100 dark:bg-gray-800'
    }
}

export const getConnectionStatusColor = (onlineCount: number, totalCount: number) => {
    if (onlineCount === totalCount) {
        return 'text-green-600 dark:text-green-400 bg-green-100 dark:bg-green-900/30'
    }
    if (onlineCount === 0) {
        return 'text-red-600 dark:text-red-400 bg-red-100 dark:bg-red-900/30'
    }
    return 'text-yellow-600 dark:text-yellow-400 bg-yellow-100 dark:bg-yellow-900/30'
}
