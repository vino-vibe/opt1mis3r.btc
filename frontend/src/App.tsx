import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { useGlobalState } from './store/globalState'
import { Dashboard } from './pages/Dashboard'
import { Packs } from './pages/Packs'
import { Claims } from './pages/Claims'
import { Boosts } from './pages/Boosts'
import { Passes } from './pages/Passes'
import { Players } from './pages/Players'
import { Watchlists } from './pages/Watchlists'

const NAV = [
  { to: '/',           label: 'Dashboard',    end: true  },
  { to: '/packs',      label: 'Buy Packs',    end: false },
  { to: '/claims',     label: 'Claims',       end: false },
  { to: '/boosts',     label: 'Boosts',       end: false },
  { to: '/passes',     label: 'List Passes',  end: false },
  { to: '/players',    label: 'Get Players',  end: false },
  { to: '/watchlists', label: 'Watchlists',   end: false },
]

export function App() {
  const { setAccounts, setAccount } = useGlobalState()

  useEffect(() => {
    fetch('/api/status/accounts')
      .then((r) => r.json())
      .then((names: string[]) => {
        setAccounts(names)
        if (names.length > 0) setAccount(names[0])
      })
      .catch(console.error)
  }, [setAccounts, setAccount])

  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
        <nav className="w-48 bg-gray-900 border-r border-gray-800 flex flex-col p-3 gap-0.5 flex-shrink-0">
          <div className="text-blue-400 font-bold text-lg px-3 py-2 mb-2 tracking-tight">
            opt1mis3r
          </div>
          {NAV.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `px-3 py-2 rounded text-sm transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white font-medium'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/"           element={<Dashboard />} />
            <Route path="/packs"      element={<Packs />} />
            <Route path="/claims"     element={<Claims />} />
            <Route path="/boosts"     element={<Boosts />} />
            <Route path="/passes"     element={<Passes />} />
            <Route path="/players"    element={<Players />} />
            <Route path="/watchlists" element={<Watchlists />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
