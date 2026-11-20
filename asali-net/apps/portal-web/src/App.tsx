import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, useEffect } from 'react'
import { Link, Route, Routes } from 'react-router'
import { api } from './api/client'
import type { Config } from './api/types'
import { NetworkStatus } from './components/NetworkStatus'
import { ThemeSwitch } from './components/ThemeSwitch'
import { EmptyState, ProblemMessage, Skeleton } from './components/ui'
import { Check, History, Report, ResultPage } from './screens/consumer'
import { NetworkPage } from './screens/lists'

// The staff portals are only downloaded by staff; a customer's phone gets the consumer screens alone.
const StaffApp = lazy(() => import('./StaffApp'))

function ConsumerApp({ config }: { config: Config }) {
  return (
    <div className="min-h-screen">
      {config.mode === 'simulation' && <div className="bg-unk-bg px-4 py-1.5 text-center text-sm text-unk-fg">Simulation: all organisations are running on this computer</div>}
      <header className="mx-auto flex max-w-[560px] flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2">
        <p className="font-semibold">Asali · Check a medicine · {config.city}</p>
        <nav aria-label="Main" className="flex items-center gap-1 text-sm">
          <Link className="inline-flex min-h-11 items-center px-2 underline" to="/history">My checks</Link>
          <Link className="inline-flex min-h-11 items-center px-2 underline" to="/report">Report a problem</Link>
        </nav>
      </header>
      <main className="mx-auto max-w-[560px] px-4 py-6">
        <Routes>
          <Route path="/" element={<Check config={config} />} />
          <Route path="result/:id" element={<ResultPage />} />
          <Route path="report" element={<Report config={config} />} />
          <Route path="history" element={<History />} />
          <Route path="network" element={<NetworkPage />} />
          <Route path="*" element={<EmptyState title="Page not found" text="Go back and check a medicine." action={<Link className="underline" to="/">Check a medicine</Link>} />} />
        </Routes>
      </main>
      <footer className="mx-auto grid max-w-[560px] gap-4 px-4 pb-8"><NetworkStatus /><ThemeSwitch /></footer>
    </div>
  )
}

export default function App() {
  const config = useQuery({ queryKey: ['config'], queryFn: () => api<Config>('/api/config') })
  useEffect(() => {
    if (config.data) {
      document.documentElement.dataset.portal = config.data.org_type
      document.title = config.data.org_type === 'consumer' ? 'Asali · Check a medicine' : `${config.data.name} · Asali`
    }
  }, [config.data])
  if (config.isPending) return <main className="mx-auto max-w-sm px-4 py-10"><Skeleton rows={2} label="Opening the portal…" /></main>
  if (config.isError) return <main className="mx-auto max-w-xl px-4 py-10"><ProblemMessage error={config.error} /></main>
  return config.data.org_type === 'consumer' ? <ConsumerApp config={config.data} /> : <Suspense fallback={<main className="mx-auto max-w-sm px-4 py-10"><Skeleton rows={2} label="Opening the portal…" /></main>}><StaffApp config={config.data} /></Suspense>
}
