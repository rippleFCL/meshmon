export default function FocusBanner({ focusedNodeId, onExit }: { focusedNodeId: string, onExit: () => void }) {
    return (
        <div className="flex justify-between items-center p-2 rounded-md bg-amber-50 dark:bg-amber-900/30 border border-amber-200 dark:border-amber-800">
            <span className="text-amber-700 dark:text-amber-300 font-medium">Focus: {focusedNodeId}</span>
            <button onClick={onExit} className="px-2 py-1 text-xs rounded bg-amber-600 text-white hover:bg-amber-700">Exit focus</button>
        </div>
    )
}
