import { useState, useCallback } from 'react'
import { useGlobalState } from '../store/globalState'
import { useStream } from '../hooks/useStream'
import { Terminal } from '../components/Terminal'
import { AccountSelector } from '../components/AccountSelector'
import { LiveToggle } from '../components/LiveToggle'
import { RunButton } from '../components/RunButton'

export function Packs() {
  const [lines, setLines] = useState<string[]>([])
  const { account, allAccounts, live } = useGlobalState()

  const onLine = useCallback((line: string) => {
    setLines((prev) => [...prev, line])
  }, [])

  const { start, cancel, running } = useStream(onLine)

  function handleRun() {
    setLines([])
    const p = new URLSearchParams()
    if (allAccounts) p.set('all_accounts', 'true')
    else if (account) p.set('account', account)
    if (live) p.set('live', 'true')
    start(`/api/run/buy-packs?${p}`)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-100">Buy Packs</h1>
      <p className="text-gray-500 text-sm">
        Buys the daily 200-rax pack for each player on the buy watchlist.
      </p>
      <div className="flex flex-wrap items-center gap-4">
        <AccountSelector />
        <LiveToggle />
        <RunButton running={running} onRun={handleRun} onCancel={cancel} label="Run Buy Packs" />
      </div>
      <Terminal lines={lines} />
    </div>
  )
}
