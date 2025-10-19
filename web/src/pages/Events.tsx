import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Info, AlertCircle } from 'lucide-react'
import { useTheme } from '../contexts/ThemeContext'
import { useRefresh } from '../contexts/RefreshContext'
import { eventsApi } from '../api/events'
import type { EventApi, ApiEvent, ApiEventType } from '../types/events'

function badgeClasses(t: ApiEventType): string {
    switch (t) {
        case 'error':
            return 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
        case 'warning':
            return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-300'
        case 'info':
        default:
            return 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300'
    }
}

function IconForType({ t }: { t: ApiEventType }) {
    if (t === 'error') return <AlertTriangle className="h-5 w-5 text-red-500" />
    if (t === 'warning') return <AlertCircle className="h-5 w-5 text-yellow-500" />
    return <Info className="h-5 w-5 text-blue-500" />
}

export default function EventsPage() {
    const { isDark } = useTheme()
    const { registerRefreshCallback } = useRefresh()
    const [data, setData] = useState<EventApi | null>(null)
    const [loading, setLoading] = useState(true)
    const [refreshing, setRefreshing] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const load = async (initial = false) => {
            try {
                if (initial) setLoading(true)
                else setRefreshing(true)
                const res = await eventsApi.getEvents()
                setData(res.data)
                setError(null)
            } catch (e) {
                console.error(e)
                setError('Failed to fetch events')
            } finally {
                if (initial) setLoading(false)
                else setRefreshing(false)
            }
        }

        const doRefresh = () => load(false)
        load(true)
        const cleanup = registerRefreshCallback(doRefresh)
        const interval = setInterval(() => load(false), 5000)
        return () => { clearInterval(interval); cleanup() }
    }, [registerRefreshCallback])

    const events = useMemo(() => {
        const arr = data?.events ?? []
        // Newest first by ISO datetime 'date'
        return [...arr].sort((a, b) => Date.parse(b.date) - Date.parse(a.date))
    }, [data])
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>Events</h1>
                    <p className={`${isDark ? 'text-gray-300' : 'text-gray-600'}`}>Live server events</p>
                </div>
                {refreshing && (
                    <div className={`flex items-center space-x-2 text-sm ${isDark ? 'text-gray-400' : 'text-gray-600'}`}>
                        <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin"></div>
                        <span>Updating...</span>
                    </div>
                )}
            </div>

            {loading && (
                <div className="card p-6">
                    <div className="flex items-center space-x-3 text-gray-600 dark:text-gray-300">
                        <Info className="h-5 w-5" />
                        <span>Loading events...</span>
                    </div>
                </div>
            )}

            {error && (
                <div className="card p-6 border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300">
                    <div className="flex items-center space-x-2">
                        <AlertTriangle className="h-5 w-5" />
                        <span>{error}</span>
                    </div>
                </div>
            )}

            {!loading && !error && (
                <div className="card p-0 overflow-hidden">
                    {events.length === 0 ? (
                        <div className={`p-6 ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>No events yet.</div>
                    ) : (
                        <ul className="divide-y divide-gray-200 dark:divide-gray-700">
                            {events.map((ev: ApiEvent, idx: number) => (
                                <li key={idx} className={`p-4 flex items-start gap-3 ${isDark ? 'bg-gray-800' : 'bg-white'}`}>
                                    <div className="mt-0.5"><IconForType t={ev.event_type} /></div>
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <span className={`text-xs px-2 py-0.5 rounded-full ${badgeClasses(ev.event_type)}`}>{ev.event_type.toUpperCase?.() || String(ev.event_type)}</span>
                                            <h3 className={`font-medium ${isDark ? 'text-white' : 'text-gray-900'}`}>{ev.title}</h3>
                                            <span className={`text-xs ${isDark ? 'text-gray-400' : 'text-gray-500'}`}>
                                                {new Date(ev.date).toLocaleString()}
                                            </span>
                                        </div>
                                        <p className={`${isDark ? 'text-gray-300' : 'text-gray-700'} mt-1 whitespace-pre-wrap break-words`}>{ev.message}</p>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    )
}
