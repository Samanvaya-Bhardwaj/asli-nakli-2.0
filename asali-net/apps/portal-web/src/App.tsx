import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, useEffect } from 'react'
import { Link, Route, Routes } from 'react-router'
import { api } from './api/client'
import type { Config } from './api/types'
import { Brand } from './components/Mark'
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
      {config.mode === 'simulation' && <div className="hatch bg-unk-bg px-4 py-1.5 text-center text-sm font-medium text-unk-fg">Simulation: all organisations are running on this computer</div>}
      <header className="z-10 bg-[var(--nav-bg)] md:sticky md:top-0 shadow-[inset_0_-1px_0_var(--border)] backdrop-blur-xl">
        <div className="mx-auto flex min-h-16 max-w-[640px] flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2">
          <p className="min-w-0"><Brand>Check a medicine · {config.city}</Brand></p>
          <nav aria-label="Main" className="flex items-center gap-1.5 text-sm font-medium">
            <Link className="inline-flex min-h-11 items-center rounded-full px-4 text-muted transition-colors duration-150 hover:bg-surface-2 hover:text-ink" to="/history">My checks</Link>
            <Link className="inline-flex min-h-11 items-center rounded-full px-4 shadow-[inset_0_0_0_1px_var(--border-strong)] transition-colors duration-150 hover:bg-surface-2" to="/report">Report a problem</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-[640px] px-4 py-8 md:py-12">
        <Routes>
          <Route path="/" element={<Check config={config} />} />
          <Route path="result/:id" element={<ResultPage />} />
          <Route path="report" element={<Report config={config} />} />
          <Route path="history" element={<History />} />
          <Route path="network" element={<NetworkPage />} />
          <Route path="*" element={<EmptyState title="Page not found" text="Go back and check a medicine." action={<Link className="underline" to="/">Check a medicine</Link>} />} />
        </Routes>
      </main>
      <footer className="mx-auto flex max-w-[640px] flex-wrap items-center justify-between gap-4 px-4 pb-10 pt-4">
        <ThemeSwitch />
        <NetworkStatus />
      </footer>
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
