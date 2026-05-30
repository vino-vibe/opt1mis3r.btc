import { create } from 'zustand'

interface GlobalState {
  account: string
  allAccounts: boolean
  live: boolean
  accounts: string[]
  setAccount: (a: string) => void
  setAllAccounts: (b: boolean) => void
  setLive: (b: boolean) => void
  setAccounts: (a: string[]) => void
}

export const useGlobalState = create<GlobalState>((set) => ({
  account: '',
  allAccounts: false,
  live: false,
  accounts: [],
  setAccount: (account) => set({ account, allAccounts: false }),
  setAllAccounts: (allAccounts) => set({ allAccounts }),
  setLive: (live) => set({ live }),
  setAccounts: (accounts) => set({ accounts }),
}))
