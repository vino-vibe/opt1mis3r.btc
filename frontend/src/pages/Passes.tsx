import { useState, useCallback } from 'react'
import { useGlobalState } from '../store/globalState'
import { useStream } from '../hooks/useStream'
import { Terminal } from '../components/Terminal'
import { AccountSelector } from '../components/AccountSelector'
import { LiveToggle } from '../components/LiveToggle'
import { RunButton } from '../components/RunButton'

export function Passes() {
  const [lines, setLines] = useState<string[]>([])
  const { account, live } = useGlobalState()

  const onLine = useCallback((line: string) => setLines((p) => [...p, line]), [])
  const { start, cancel, running } = useStream(onLine)

  function handleRun() {
    setLines([])
    const p = new URLSearchParams()
    if (account) p.set('account', account)
    if (live) p.set('live', 'true')
    start(`/api/run/list-pass?${p}`)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-100">List Passes</h1>
      <p className="text-gray-500 text-sm">
        Lists passes from the list watchlist on the marketplace using meowbot pricing. Min rarity: Rare (≥80).
      </p>
      <div className="flex flex-wrap items-center gap-4">
        <AccountSelector />
        <LiveToggle />
        <RunButton running={running} onRun={handleRun} onCancel={cancel} label="Run List Passes" />
      </div>
      <Terminal lines={lines} />
    </div>
  )
}
