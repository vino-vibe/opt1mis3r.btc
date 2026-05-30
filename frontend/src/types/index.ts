export interface BuyEntry {
  label: string
  entityId: number
  sport: string
  season: number
  enabled: boolean
}

export interface BoostEntry {
  label: string
  entityId: number
  sport: string
  season: number
  preferred_stat: string
  fallback_stat?: string
  rarity: number
  enabled: boolean
}

export interface ListEntry {
  label: string
  cardId: number
  entityId: number
  sport: string
  season: number
  enabled: boolean
}

export type WatchlistType = 'buy' | 'boost' | 'list'
export type WatchlistEntry = BuyEntry | BoostEntry | ListEntry

export interface AccountStatus {
  bought: number | null
  boosted: number | null
  listed: number | null
  claims_fetched: boolean
}

export interface TodayStatus {
  date: string
  accounts: Record<string, AccountStatus>
}
