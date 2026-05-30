import { useGlobalState } from '../store/globalState'

export function LiveToggle() {
  const { live, setLive } = useGlobalState()

  return (
    <div className="flex items-center gap-2">
      <span className="text-gray-500 text-sm">Dry Run</span>
      <button
        onClick={() => setLive(!live)}
        className={`relative w-10 h-5 rounded-full transition-colors ${live ? 'bg-red-600' : 'bg-gray-600'}`}
      >
        <span
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            live ? 'translate-x-5' : 'translate-x-0.5'
          }`}
        />
      </button>
      <span className={`text-sm font-semibold ${live ? 'text-red-400' : 'text-gray-500'}`}>
        {live ? 'LIVE' : 'Off'}
      </span>
      {live && <span className="text-xs text-red-500">⚠ real writes enabled</span>}
    </div>
  )
}
