interface Props {
  running: boolean
  onRun: () => void
  onCancel: () => void
  label: string
}

export function RunButton({ running, onRun, onCancel, label }: Props) {
  if (running) {
    return (
      <button
        onClick={onCancel}
        className="flex items-center gap-2 px-4 py-2 bg-red-700 hover:bg-red-600 text-white rounded text-sm font-medium transition-colors"
      >
        <span className="w-2 h-2 rounded-full bg-red-300 animate-pulse" />
        Cancel
      </button>
    )
  }
  return (
    <button
      onClick={onRun}
      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm font-medium transition-colors"
    >
      {label}
    </button>
  )
}
