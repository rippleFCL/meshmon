import React, { createContext, useContext, useState, useCallback, useRef } from 'react'

interface RefreshContextType {
    isRefreshing: boolean
    triggerRefresh: () => void
    registerRefreshCallback: (callback: () => void) => () => void
}

const RefreshContext = createContext<RefreshContextType | undefined>(undefined)

export function RefreshProvider({ children }: { children: React.ReactNode }) {
    const [isRefreshing, setIsRefreshing] = useState(false)
    const callbacksRef = useRef<Set<() => void>>(new Set())

    const triggerRefresh = useCallback(() => {
        setIsRefreshing(true)
        callbacksRef.current.forEach(callback => {
            try {
                callback()
            } catch (error) {
                console.error('Error in refresh callback:', error)
            }
        })
        // Reset refreshing state after a delay
        setTimeout(() => setIsRefreshing(false), 1000)
    }, [])

    const registerRefreshCallback = useCallback((callback: () => void) => {
        callbacksRef.current.add(callback)

        // Return cleanup function
        return () => {
            callbacksRef.current.delete(callback)
        }
    }, [])

    return (
        <RefreshContext.Provider value={{
            isRefreshing,
            triggerRefresh,
            registerRefreshCallback
        }}>
            {children}
        </RefreshContext.Provider>
    )
}

export function useRefresh() {
    const context = useContext(RefreshContext)
    if (context === undefined) {
        throw new Error('useRefresh must be used within a RefreshProvider')
    }
    return context
}
