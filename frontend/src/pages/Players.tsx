import { useState, useCallback } from 'react'
import { useStream } from '../hooks/useStream'
import { Terminal } from '../components/Terminal'
import { RunButton } from '../components/RunButton'

export function Players() {
  const [lines, setLines] = useState<string[]>([])

  const onLine = useCallback((line: string) => setLines((p) => [...p, line]), [])
  const { start, cancel, running } = useStream(onLine)

  function handleRun() {
    setLines([])
    start('/api/run/get-players')
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-100">Get Players</h1>
      <p className="text-gray-500 text-sm">
        Syncs player pass data for all accounts and sports. Required before running boosts (resolves entityId → cardId).
      </p>
      <div className="flex items-center gap-4">
        <RunButton running={running} onRun={handleRun} onCancel={cancel} label="Sync Players" />
      </div>
      <Terminal lines={lines} />
    </div>
  )
}
