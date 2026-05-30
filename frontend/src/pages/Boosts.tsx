import { useState, useCallback } from 'react'
import { useGlobalState } from '../store/globalState'
import { useStream } from '../hooks/useStream'
import { Terminal } from '../components/Terminal'
import { AccountSelector } from '../components/AccountSelector'
import { LiveToggle } from '../components/LiveToggle'
import { RunButton } from '../components/RunButton'

const SPORTS = ['', 'wnba', 'mlb', 'nba', 'nhl', 'golf']

export function Boosts() {
  const [lines, setLines] = useState<string[]>([])
  const [sport, setSport] = useState('')
  const { account, allAccounts, live } = useGlobalState()

  const onLine = useCallback((line: string) => setLines((p) => [...p, line]), [])
  const { start, cancel, running } = useStream(onLine)

  function handleRun() {
    setLines([])
    const p = new URLSearchParams()
    if (allAccounts) p.set('all_accounts', 'true')
    else if (account) p.set('account', account)
    if (live) p.set('live', 'true')
    if (sport) p.set('sport', sport)
    start(`/api/run/boost?${p}`)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-100">Apply Boosts</h1>
      <p className="text-gray-500 text-sm">
        Applies stat boosts from the boost watchlist. Skips if already boosted today.
      </p>
      <div className="flex flex-wrap items-center gap-4">
        <AccountSelector />
        <div className="flex items-center gap-2">
          <label className="text-gray-400 text-sm">Sport</label>
          <select
            className="bg-gray-800 text-gray-100 rounded px-3 py-1.5 text-sm border border-gray-700"
            value={sport}
            onChange={(e) => setSport(e.target.value)}
          >
            {SPORTS.map((s) => (
              <option key={s} value={s}>{s || 'All Sports'}</option>
            ))}
          </select>
        </div>
        <LiveToggle />
        <RunButton running={running} onRun={handleRun} onCancel={cancel} label="Run Boosts" />
      </div>
      <Terminal lines={lines} />
    </div>
  )
}
