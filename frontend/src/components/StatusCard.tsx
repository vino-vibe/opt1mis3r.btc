import { AccountStatus } from '../types'

interface Props {
  accountName: string
  status: AccountStatus
}

function Stat({ label, value }: { label: string; value: number | null | boolean }) {
  const isNull = value === null
  const display = isNull ? '—' : typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)
  const color = isNull
    ? 'text-gray-600'
    : value === 0 || value === false
    ? 'text-yellow-500'
    : 'text-green-400'

  return (
    <div className="flex flex-col items-center">
      <span className={`text-xl font-bold ${color}`}>{display}</span>
      <span className="text-xs text-gray-500 mt-0.5">{label}</span>
    </div>
  )
}

export function StatusCard({ accountName, status }: Props) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 min-w-[180px]">
      <h3 className="text-gray-300 font-semibold text-sm tracking-wide mb-3">{accountName}</h3>
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Bought" value={status.bought} />
        <Stat label="Boosted" value={status.boosted} />
        <Stat label="Listed" value={status.listed} />
        <Stat label="Claims" value={status.claims_fetched} />
      </div>
    </div>
  )
}
