import { useState } from 'react'
import { WatchlistType } from '../types'
import { WatchlistEditor } from '../components/WatchlistEditor'

const TABS: { key: WatchlistType; label: string; description: string }[] = [
  { key: 'buy', label: 'Buy Packs', description: 'Players to buy daily 200-rax packs for' },
  { key: 'boost', label: 'Boosts', description: 'Players to apply stat boosts to' },
  { key: 'list', label: 'Listings', description: 'Passes to list on the marketplace' },
]

export function Watchlists() {
  const [active, setActive] = useState<WatchlistType>('buy')
  const current = TABS.find((t) => t.key === active)!

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-100">Watchlists</h1>
      <div className="flex gap-2">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActive(key)}
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
              active === key
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <p className="text-gray-500 text-sm">{current.description}</p>
      <WatchlistEditor type={active} />
    </div>
  )
}
