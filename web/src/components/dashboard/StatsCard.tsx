import { ReactNode } from 'react'
import { useTheme } from '../../contexts/ThemeContext'

interface Props {
    icon: ReactNode
    value: string | number
    label: string
    iconBgClass?: string
    iconColorClass?: string
}

export default function StatsCard({ icon, value, label, iconBgClass, iconColorClass }: Props) {
    const { isDark } = useTheme()
    const bg = iconBgClass ?? (isDark ? 'bg-blue-900' : 'bg-primary-100')
    const ic = iconColorClass ?? (isDark ? 'text-blue-400' : 'text-primary-600')
    return (
        <div className="card p-6 stats-update">
            <div className="flex items-center">
                <div className={`p-3 rounded-lg ${bg}`}>
                    <div className={`${ic}`}>{icon}</div>
                </div>
                <div className="ml-4">
                    <p className={`text-2xl font-bold ${isDark ? 'text-white' : 'text-gray-900'}`}>{value}</p>
                    <p className={`text-sm ${isDark ? 'text-gray-300' : 'text-gray-600'}`}>{label}</p>
                </div>
            </div>
        </div>
    )
}
