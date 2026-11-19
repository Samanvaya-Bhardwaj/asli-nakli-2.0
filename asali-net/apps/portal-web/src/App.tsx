import { useQuery } from '@tanstack/react-query'
import { useEffect } from 'react'
import { Link, Navigate, Route, Routes } from 'react-router'
import { api, ApiError } from './api/client'
import type { Config, Me } from './api/types'
import { NetworkStatus } from './components/NetworkStatus'
import { Shell } from './components/Shell'
import { EmptyState, ProblemMessage, Skeleton } from './components/ui'
import { Documents } from './screens/Documents'
import { Login } from './screens/Login'
import { ScanSession } from './screens/ScanSession'
import { Check, History, Report, ResultPage } from './screens/consumer'
import { Activity, IncomingList, NetworkPage, StockList } from './screens/lists'
import { Batches, Labels, Products, Recalls } from './screens/pharma'
import { AlertsRegulator, AlertsShop, Complaints, Investigate, Licences } from './screens/regulator'

const HOME = { pharma: '/dispatch', distributor: '/receive', shop: '/sell', regulator: '/investigate', consumer: '/' } as const

function StaffRoutes({ config }: { config: Config }) {
  const common = (
    <>
      <Route path="documents" element={<Documents />} />
      <Route path="network" element={<NetworkPage />} />
      <Route path="*" element={<EmptyState title="Page not found" text="This page does not exist in this portal. Use the menu to go back." />} />
    </>
  )
  switch (config.org_type) {
    case 'pharma':
      return (
        <Routes>
          <Route path="dispatch" element={<ScanSession kind="dispatch" config={config} />} />
          <Route path="batches" element={<Batches />} />
          <Route path="labels/*" element={<Labels />} />
          <Route path="products" element={<Products />} />
          <Route path="recalls" element={<Recalls />} />
          <Route path="activity" element={<Activity />} />
          {common}
        </Routes>
      )
    case 'distributor':
      return (
        <Routes>
          <Route path="receive" element={<IncomingList />} />
          <Route path="receive/:from/:ref" element={<ScanSession kind="receive" config={config} />} />
          <Route path="dispatch" element={<ScanSession kind="dispatch" config={config} />} />
          <Route path="stock" element={<StockList />} />
          <Route path="activity" element={<Activity />} />
          {common}
        </Routes>
      )
    case 'shop':
      return (
        <Routes>
          <Route path="sell" element={<ScanSession kind="sell" config={config} />} />
          <Route path="receive" element={<IncomingList />} />
          <Route path="receive/:from/:ref" element={<ScanSession kind="receive" config={config} />} />
          <Route path="returns" element={<ScanSession kind="return" config={config} />} />
          <Route path="stock" element={<StockList />} />
          <Route path="alerts" element={<AlertsShop />} />
          {common}
        </Routes>
      )
    default:
      return (
        <Routes>
          <Route path="investigate" element={<Investigate />} />
          <Route path="complaints" element={<Complaints />} />
          <Route path="alerts" element={<AlertsRegulator />} />
          <Route path="licences" element={<Licences />} />
          {common}
        </Routes>
      )
  }
}

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
      <footer className="mx-auto max-w-[560px] px-4 pb-8"><NetworkStatus /></footer>
    </div>
  )
}

function StaffApp({ config }: { config: Config }) {
  const me = useQuery({
    queryKey: ['me'],
    queryFn: () => api<Me>('/api/me'),
    retry: false,
  })
  if (me.isPending) return <main className="mx-auto max-w-sm px-4 py-10"><Skeleton rows={2} label="Opening the portal…" /></main>
  if (me.isError) {
    if (me.error instanceof ApiError && me.error.problem.status === 401) return <Login config={config} />
    return <main className="mx-auto max-w-xl px-4 py-10"><ProblemMessage error={me.error} /></main>
  }
  return (
    <Routes>
      <Route element={<Shell config={config} me={me.data} />}>
        <Route index element={<Navigate to={HOME[config.org_type]} replace />} />
        <Route path="*" element={<StaffRoutes config={config} />} />
      </Route>
    </Routes>
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
  return config.data.org_type === 'consumer' ? <ConsumerApp config={config.data} /> : <StaffApp config={config.data} />
}
