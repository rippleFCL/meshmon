export default function FocusBanner({ focusedNodeId, focusedLabel, onExit }: { focusedNodeId: string, focusedLabel?: string, onExit: () => void }) {
    const title = focusedLabel || focusedNodeId
    return (
        <div className="flex justify-between items-center p-2 rounded-md bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800">
            <span className="text-amber-700 dark:text-amber-300 font-medium">Focus: {title}</span>
            <button onClick={onExit} className="px-2 py-1 text-xs rounded bg-amber-600 text-white hover:bg-amber-700">Exit focus</button>
        </div>
    )
}
