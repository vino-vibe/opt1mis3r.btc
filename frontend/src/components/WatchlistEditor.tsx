import { useEffect, useState } from 'react'
import { WatchlistType } from '../types'

interface Props {
  type: WatchlistType
}

const SPORT_OPTIONS = ['wnba', 'mlb', 'nba', 'nhl', 'golf']
const STAT_OPTIONS = ['PTS', 'AST', 'REB', 'STL', 'BLK', '3PM', 'K', 'R', 'RBI', '2B', 'HR_3B', 'EAGLE', 'BIRDIE', 'auto']

export function WatchlistEditor({ type }: Props) {
  const [entries, setEntries] = useState<Record<string, unknown>[]>([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [newEntry, setNewEntry] = useState<Record<string, string | number | boolean>>({})

  async function load() {
    setLoading(true)
    const res = await fetch(`/api/watchlists/${type}`)
    const data = await res.json()
    setEntries(data)
    setLoading(false)
  }

  useEffect(() => { load() }, [type])

  async function toggleEnabled(index: number, current: boolean) {
    await fetch(`/api/watchlists/${type}/${index}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !current }),
    })
    load()
  }

  async function deleteEntry(index: number) {
    await fetch(`/api/watchlists/${type}/${index}`, { method: 'DELETE' })
    load()
  }

  async function addEntry() {
    await fetch(`/api/watchlists/${type}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newEntry),
    })
    setNewEntry({})
    setAdding(false)
    load()
  }

  if (loading) return <div className="text-gray-500 text-sm">Loading...</div>

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b border-gray-800">
              <th className="pb-2 pr-4">Label</th>
              <th className="pb-2 pr-4">Sport</th>
              <th className="pb-2 pr-4">Season</th>
              <th className="pb-2 pr-4">EntityId</th>
              {type === 'list' && <th className="pb-2 pr-4">CardId</th>}
              {type === 'boost' && (
                <>
                  <th className="pb-2 pr-4">Stat</th>
                  <th className="pb-2 pr-4">Fallback</th>
                  <th className="pb-2 pr-4">Rarity</th>
                </>
              )}
              <th className="pb-2 pr-4">Enabled</th>
              <th className="pb-2"></th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, i) => (
              <tr key={i} className={`border-b border-gray-900 ${!entry.enabled ? 'opacity-40' : ''}`}>
                <td className="py-2 pr-4 text-gray-200">{String(entry.label ?? '')}</td>
                <td className="py-2 pr-4 text-gray-400">{String(entry.sport ?? '')}</td>
                <td className="py-2 pr-4 text-gray-400">{String(entry.season ?? '')}</td>
                <td className="py-2 pr-4 text-gray-500">{String(entry.entityId ?? '')}</td>
                {type === 'list' && <td className="py-2 pr-4 text-gray-500">{String(entry.cardId ?? '')}</td>}
                {type === 'boost' && (
                  <>
                    <td className="py-2 pr-4 text-blue-400">{String(entry.preferred_stat ?? '')}</td>
                    <td className="py-2 pr-4 text-gray-500">{String(entry.fallback_stat ?? '—')}</td>
                    <td className="py-2 pr-4 text-gray-400">{String(entry.rarity ?? 3)}</td>
                  </>
                )}
                <td className="py-2 pr-4">
                  <button
                    onClick={() => toggleEnabled(i, Boolean(entry.enabled))}
                    className={`w-8 h-4 rounded-full transition-colors ${entry.enabled ? 'bg-green-600' : 'bg-gray-700'}`}
                  >
                    <span className={`block w-3 h-3 rounded-full bg-white transition-transform mx-0.5 ${entry.enabled ? 'translate-x-4' : 'translate-x-0'}`} />
                  </button>
                </td>
                <td className="py-2">
                  <button
                    onClick={() => deleteEntry(i)}
                    className="text-gray-600 hover:text-red-400 text-xs transition-colors"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {adding ? (
        <div className="bg-gray-900 rounded-lg p-4 space-y-3">
          <p className="text-gray-400 text-sm font-medium">New entry</p>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="Label"
              className="bg-gray-800 text-gray-100 px-3 py-1.5 rounded text-sm border border-gray-700"
              onChange={(e) => setNewEntry((p) => ({ ...p, label: e.target.value }))}
            />
            <select
              className="bg-gray-800 text-gray-100 px-3 py-1.5 rounded text-sm border border-gray-700"
              onChange={(e) => setNewEntry((p) => ({ ...p, sport: e.target.value }))}
              defaultValue=""
            >
              <option value="" disabled>Sport</option>
              {SPORT_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <input
              placeholder="Season (e.g. 2026)"
              type="number"
              className="bg-gray-800 text-gray-100 px-3 py-1.5 rounded text-sm border border-gray-700"
              onChange={(e) => setNewEntry((p) => ({ ...p, season: parseInt(e.target.value) }))}
            />
            <input
              placeholder="EntityId"
              type="number"
              className="bg-gray-800 text-gray-100 px-3 py-1.5 rounded text-sm border border-gray-700"
              onChange={(e) => setNewEntry((p) => ({ ...p, entityId: parseInt(e.target.value) }))}
            />
            {type === 'list' && (
              <input
                placeholder="CardId"
                type="number"
                className="bg-gray-800 text-gray-100 px-3 py-1.5 rounded text-sm border border-gray-700"
                onChange={(e) => setNewEntry((p) => ({ ...p, cardId: parseInt(e.target.value) }))}
              />
            )}
            {type === 'boost' && (
              <>
                <select
                  className="bg-gray-800 text-gray-100 px-3 py-1.5 rounded text-sm border border-gray-700"
                  onChange={(e) => setNewEntry((p) => ({ ...p, preferred_stat: e.target.value }))}
                  defaultValue=""
                >
                  <option value="" disabled>Preferred stat</option>
                  {STAT_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <select
                  className="bg-gray-800 text-gray-100 px-3 py-1.5 rounded text-sm border border-gray-700"
                  onChange={(e) => setNewEntry((p) => ({ ...p, fallback_stat: e.target.value || undefined }))}
                  defaultValue=""
                >
                  <option value="">No fallback</option>
                  {STAT_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <select
                  className="bg-gray-800 text-gray-100 px-3 py-1.5 rounded text-sm border border-gray-700"
                  onChange={(e) => setNewEntry((p) => ({ ...p, rarity: parseInt(e.target.value) }))}
                  defaultValue="3"
                >
                  <option value="3">3 — Rare</option>
                  <option value="4">4 — Epic</option>
                  <option value="5">5 — Legendary</option>
                </select>
              </>
            )}
          </div>
          <div className="flex gap-2">
            <button
              onClick={addEntry}
              className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-sm"
            >
              Add
            </button>
            <button
              onClick={() => { setAdding(false); setNewEntry({}) }}
              className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setAdding(true)}
          className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
        >
          + Add entry
        </button>
      )}
    </div>
  )
}
