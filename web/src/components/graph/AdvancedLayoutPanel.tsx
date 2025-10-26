import { useMemo } from 'react'

export type ForcedAdvancedOptions = {
    elkQuality: 'default' | 'proof'
    iterations: number
    minEdgeLength: number
    aspectRatio: number
}

export default function AdvancedLayoutPanel({
    layoutMode,
    value,
    onChange,
    isDark,
    onRecompute,
    onReset,
}: {
    layoutMode: 'forced' | 'concentric' | 'dense' | 'pretty'
    value: { forced: ForcedAdvancedOptions }
    onChange: (next: { forced: ForcedAdvancedOptions }) => void
    isDark: boolean
    onRecompute: () => void
    onReset: () => void
}) {
    const forcedOpts = value.forced
    const wrap = useMemo(() => (label: string, children: React.ReactNode) => (
        <label className="flex items-center justify-between gap-2 text-[12px]">
            <span className={isDark ? 'text-gray-200' : 'text-gray-700'}>{label}</span>
            <span className="inline-flex items-center gap-2">{children}</span>
        </label>
    ), [isDark])

    return (
        <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
            <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-1.5">Advanced layout</div>

            {layoutMode === 'forced' && (
                <div className="space-y-2">
                    {wrap('Quality', (
                        <select
                            className={`px-1.5 py-1 rounded ${isDark ? 'bg-gray-800 text-gray-200 border-gray-700' : 'bg-white text-gray-800 border-gray-300'} border`}
                            value={forcedOpts.elkQuality}
                            onChange={(e) => onChange({
                                forced: { ...forcedOpts, elkQuality: (e.target.value as any) }
                            })}
                        >
                            <option value="default">Default</option>
                            <option value="proof">Proof (higher)</option>
                        </select>
                    ))}

                    {wrap('Iterations', (
                        <input
                            type="number"
                            className={`w-24 px-2 py-1 rounded ${isDark ? 'bg-gray-800 text-gray-200 border-gray-700' : 'bg-white text-gray-800 border-gray-300'} border`}
                            min={200}
                            max={5000}
                            step={100}
                            value={forcedOpts.iterations}
                            onChange={(e) => onChange({ forced: { ...forcedOpts, iterations: Math.max(200, Math.min(5000, Number(e.target.value) || 1200)) } })}
                        />
                    ))}

                    {wrap('Min edge length', (
                        <input
                            type="number"
                            className={`w-24 px-2 py-1 rounded ${isDark ? 'bg-gray-800 text-gray-200 border-gray-700' : 'bg-white text-gray-800 border-gray-300'} border`}
                            min={10}
                            max={600}
                            step={10}
                            value={forcedOpts.minEdgeLength}
                            onChange={(e) => onChange({ forced: { ...forcedOpts, minEdgeLength: Math.max(10, Math.min(600, Number(e.target.value) || 120)) } })}
                        />
                    ))}

                    {wrap('Aspect ratio', (
                        <input
                            type="number"
                            className={`w-24 px-2 py-1 rounded ${isDark ? 'bg-gray-800 text-gray-200 border-gray-700' : 'bg-white text-gray-800 border-gray-300'} border`}
                            min={0.5}
                            max={2.0}
                            step={0.1}
                            value={forcedOpts.aspectRatio}
                            onChange={(e) => onChange({ forced: { ...forcedOpts, aspectRatio: Math.max(0.5, Math.min(2.0, Number(e.target.value) || 1.2)) } })}
                        />
                    ))}

                    <div className="flex items-center justify-between pt-2">
                        <button
                            onClick={onRecompute}
                            className={`px-2 py-1 text-xs rounded ${isDark ? 'bg-blue-700 text-white hover:bg-blue-600' : 'bg-blue-600 text-white hover:bg-blue-700'}`}
                        >
                            Recompute now
                        </button>
                        <button
                            onClick={onReset}
                            className={`px-2 py-1 text-xs rounded ${isDark ? 'bg-gray-700 text-gray-100 hover:bg-gray-600' : 'bg-gray-200 text-gray-800 hover:bg-gray-300'}`}
                            title="Reset advanced options to defaults"
                        >
                            Reset to defaults
                        </button>
                    </div>
                    <div className="text-[11px] text-gray-500 dark:text-gray-400">Changes apply on next layout compute (switch layout or refresh; focus mode ignores global layout).</div>
                </div>
            )}

            {layoutMode !== 'forced' && (
                <div className="text-[12px] text-gray-500 dark:text-gray-400">No advanced options for this layout.</div>
            )}
        </div>
    )
}
