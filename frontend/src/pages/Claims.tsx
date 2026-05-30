import { useState, useCallback } from 'react'
import { useGlobalState } from '../store/globalState'
import { useStream } from '../hooks/useStream'
import { Terminal } from '../components/Terminal'
import { AccountSelector } from '../components/AccountSelector'
import { LiveToggle } from '../components/LiveToggle'
import { RunButton } from '../components/RunButton'

export function Claims() {
  const [fetchLines, setFetchLines] = useState<string[]>([])
  const [claimLines, setClaimLines] = useState<string[]>([])
  const { account, allAccounts, live } = useGlobalState()

  const onFetchLine = useCallback((l: string) => setFetchLines((p) => [...p, l]), [])
  const onClaimLine = useCallback((l: string) => setClaimLines((p) => [...p, l]), [])

  const fetchStream = useStream(onFetchLine)
  const claimStream = useStream(onClaimLine)

  function accountParams() {
    const p = new URLSearchParams()
    if (allAccounts) {
      /* no account param = all */
    } else if (account) {
      p.set('account', account)
    }
    return p
  }

  function handleFetch() {
    setFetchLines([])
    start(`/api/run/get-claims?${accountParams()}`)
  }

  function handleClaim() {
    setClaimLines([])
    const p = accountParams()
    if (live) p.set('live', 'true')
    claimStream.start(`/api/run/do-claims?${p}`)
  }

  const { start } = fetchStream

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-100">OTD Claims</h1>
      <div className="flex flex-wrap items-center gap-4">
        <AccountSelector />
        <LiveToggle />
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <h2 className="text-gray-300 font-medium">Step 1 — Fetch</h2>
          <RunButton
            running={fetchStream.running}
            onRun={handleFetch}
            onCancel={fetchStream.cancel}
            label="Fetch Claims"
          />
        </div>
        <Terminal lines={fetchLines} />
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <h2 className="text-gray-300 font-medium">Step 2 — Claim</h2>
          <RunButton
            running={claimStream.running}
            onRun={handleClaim}
            onCancel={claimStream.cancel}
            label="Claim Earnings"
          />
        </div>
        <Terminal lines={claimLines} />
      </div>
    </div>
  )
}
