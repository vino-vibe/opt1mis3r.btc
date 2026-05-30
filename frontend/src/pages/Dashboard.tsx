import { useEffect, useState } from 'react'
import { TodayStatus } from '../types'
import { StatusCard } from '../components/StatusCard'

export function Dashboard() {
  const [status, setStatus] = useState<TodayStatus | null>(null)

  function load() {
    fetch('/api/status/today')
      .then((r) => r.json())
      .then(setStatus)
      .catch(console.error)
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-baseline gap-3">
        <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
        {status && <span className="text-gray-500 text-sm">{status.date}</span>}
        <button onClick={load} className="text-xs text-gray-600 hover:text-gray-400 ml-auto">
          Refresh
        </button>
      </div>

      {!status ? (
        <p className="text-gray-500">Loading...</p>
      ) : (
        <div className="flex flex-wrap gap-4">
          {Object.entries(status.accounts).map(([name, acct]) => (
            <StatusCard key={name} accountName={name} status={acct} />
          ))}
        </div>
      )}

      <div className="text-xs text-gray-600 mt-4">Auto-refreshes every 30s</div>
    </div>
  )
}
