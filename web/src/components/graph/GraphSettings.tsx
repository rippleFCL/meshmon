type LayoutMode = 'forced' | 'concentric' | 'dense' | 'pretty'
type AnimationMode = 'never' | 'hover' | 'always'

export default function GraphSettings({ layoutMode, setLayoutMode, hideOnlineByDefault, setHideOnlineByDefault, animationMode, setAnimationMode }: {
    layoutMode: LayoutMode
    setLayoutMode: (v: LayoutMode) => void
    hideOnlineByDefault: boolean
    setHideOnlineByDefault: (v: boolean) => void
    animationMode: AnimationMode
    setAnimationMode: (v: AnimationMode) => void
}) {
    return (
        <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
            <div className="font-medium text-gray-900 dark:text-gray-100 text-sm mb-1.5">Layout</div>
            <div className="flex items-center space-x-2 mb-2">
                <label className="text-gray-600 dark:text-gray-400">Layout:</label>
                <select
                    value={layoutMode}
                    onChange={(e) => setLayoutMode(e.target.value as LayoutMode)}
                    className="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                >
                    <option value="pretty">Golden Spiral</option>
                    <option value="concentric">Concentric</option>
                    <option value="dense">Dense Grid</option>
                    <option value="forced">Forced</option>
                </select>
            </div>
            <div className="mt-2">
                <label className="inline-flex items-center space-x-2 cursor-pointer">
                    <input type="checkbox" checked={hideOnlineByDefault} onChange={(e) => setHideOnlineByDefault(e.target.checked)} />
                    <span className="text-gray-600 dark:text-gray-400">Hide online edges (show on hover)</span>
                </label>
            </div>
            <div className="mt-2">
                <label className="text-gray-600 dark:text-gray-400 mr-2">Animate:</label>
                <select
                    value={animationMode}
                    onChange={(e) => setAnimationMode(e.target.value as AnimationMode)}
                    className="px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
                >
                    <option value="never">Never</option>
                    <option value="hover">On hover/focus</option>
                    <option value="always">Always</option>
                </select>
            </div>
        </div>
    )
}
