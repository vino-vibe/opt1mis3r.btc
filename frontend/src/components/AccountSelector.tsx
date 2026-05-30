import { useGlobalState } from '../store/globalState'

export function AccountSelector() {
  const { account, allAccounts, accounts, setAccount, setAllAccounts } = useGlobalState()

  return (
    <div className="flex items-center gap-2">
      <label className="text-gray-400 text-sm">Account</label>
      <select
        className="bg-gray-800 text-gray-100 rounded px-3 py-1.5 text-sm border border-gray-700 focus:outline-none focus:border-blue-500"
        value={allAccounts ? '__all__' : account}
        onChange={(e) => {
          if (e.target.value === '__all__') {
            setAllAccounts(true)
          } else {
            setAccount(e.target.value)
          }
        }}
      >
        <option value="__all__">All Accounts</option>
        {accounts.map((a) => (
          <option key={a} value={a}>{a}</option>
        ))}
      </select>
    </div>
  )
}
