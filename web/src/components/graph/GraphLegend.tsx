export default function GraphLegend() {
    return (
        <div>
            <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-1.5">Network Legend</div>
            <div className="space-y-1.5">
                <div className="flex items-center space-x-2">
                    <div className="w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse"></div>
                    <span className="text-gray-600 dark:text-gray-400">Online Node</span>
                </div>
                <div className="flex items-center space-x-2">
                    <div className="w-2.5 h-2.5 bg-red-500 rounded-full"></div>
                    <span className="text-gray-600 dark:text-gray-400">Offline Node</span>
                </div>
                {/* Bidirectional: both up (solid green with arrowheads both ends) */}
                <div className="flex items-center space-x-2">
                    <svg width="46" height="10" viewBox="0 0 46 10" className="shrink-0">
                        <defs>
                            <marker id="lg-bidi-up-start" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto-start-reverse">
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e" />
                            </marker>
                            <marker id="lg-bidi-up-end" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto">
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e" />
                            </marker>
                        </defs>
                        <line x1="6" y1="5" x2="40" y2="5" stroke="#22c55e" strokeWidth="2.5" markerStart="url(#lg-bidi-up-start)" markerEnd="url(#lg-bidi-up-end)" />
                    </svg>
                    <span className="text-gray-600 dark:text-gray-400">Bidirectional: up</span>
                </div>
                {/* Bidirectional: degraded (one way down) dashed yellow with red/green arrowheads */}
                <div className="flex items-center space-x-2">
                    <svg width="46" height="10" viewBox="0 0 46 10" className="shrink-0">
                        <defs>
                            <marker id="lg-bidi-deg-start" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto-start-reverse">
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                            </marker>
                            <marker id="lg-bidi-deg-end" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto">
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e" />
                            </marker>
                        </defs>
                        <line x1="6" y1="5" x2="40" y2="5" stroke="#eab308" strokeWidth="2.5" strokeDasharray="6 3" markerStart="url(#lg-bidi-deg-start)" markerEnd="url(#lg-bidi-deg-end)" />
                    </svg>
                    <span className="text-gray-600 dark:text-gray-400">Bidirectional: degraded (one-way down)</span>
                </div>
                {/* Bidirectional: down (dashed red with red arrowheads) */}
                <div className="flex items-center space-x-2">
                    <svg width="46" height="10" viewBox="0 0 46 10" className="shrink-0">
                        <defs>
                            <marker id="lg-bidi-down-start" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto-start-reverse">
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                            </marker>
                            <marker id="lg-bidi-down-end" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto">
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                            </marker>
                        </defs>
                        <line x1="6" y1="5" x2="40" y2="5" stroke="#ef4444" strokeWidth="2.5" strokeDasharray="6 3" markerStart="url(#lg-bidi-down-start)" markerEnd="url(#lg-bidi-down-end)" />
                    </svg>
                    <span className="text-gray-600 dark:text-gray-400">Bidirectional: down</span>
                </div>
                {/* Unidirectional: up (single green arrowhead) */}
                <div className="flex items-center space-x-2">
                    <svg width="46" height="10" viewBox="0 0 46 10" className="shrink-0">
                        <defs>
                            <marker id="lg-uni-up-end" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto">
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#22c55e" />
                            </marker>
                        </defs>
                        <line x1="0" y1="5" x2="40" y2="5" stroke="#22c55e" strokeWidth="2.5" markerEnd="url(#lg-uni-up-end)" />
                    </svg>
                    <span className="text-gray-600 dark:text-gray-400">Unidirectional: up</span>
                </div>
                {/* Unidirectional: down (single red arrowhead) */}
                <div className="flex items-center space-x-2">
                    <svg width="46" height="10" viewBox="0 0 46 10" className="shrink-0">
                        <defs>
                            <marker id="lg-uni-down-end" viewBox="0 0 10 10" refX="10" refY="5" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="10" orient="auto">
                                <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
                            </marker>
                        </defs>
                        <line x1="0" y1="5" x2="40" y2="5" stroke="#ef4444" strokeWidth="2.5" markerEnd="url(#lg-uni-down-end)" />
                    </svg>
                    <span className="text-gray-600 dark:text-gray-400">Unidirectional: down</span>
                </div>
                <div className="text-[10px] text-gray-500 dark:text-gray-500 pt-0.5">Arrowheads are colored per direction (green = up, red = down).</div>
            </div>
        </div>
    )
}
