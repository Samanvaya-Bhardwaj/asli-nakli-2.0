import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Ellipsis, LogOut } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { api } from '../api/client'
import type { Config, Me } from '../api/types'
import { NAV } from './nav'
import { NetworkStatus } from './NetworkStatus'
import { ThemeSwitch } from './ThemeSwitch'
import { Button } from './ui'

export function Shell({ config, me }: { config: Config; me: Me }) {
  const qc = useQueryClient()
  useEffect(() => {
    document.documentElement.dataset.portal = config.org_type
  }, [config.org_type])
  const alerts = useQuery({ queryKey: ['alerts-count'], enabled: config.org_type === 'shop', queryFn: () => api<{ alerts: unknown[] }>('/api/alerts'), refetchInterval: 60000 })
  const items = NAV[config.org_type]
  const place = config.shop ? `${config.shop.area}, ${config.city}` : config.city
  const [more, setMore] = useState(false)
  useEffect(() => {
    if (!more) return
    const close = (e: KeyboardEvent) => e.key === 'Escape' && setMore(false)
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [more])
  const logout = async () => {
    await api('/api/logout', { method: 'POST' })
    await qc.invalidateQueries({ queryKey: ['me'] })
  }
  return (
    <div className="min-h-screen md:grid md:grid-cols-[232px_1fr]">
      <aside className="hidden border-r border-line bg-surface md:flex md:flex-col">
        <div className="h-[3px] bg-accent" />
        <div className="px-4 py-4">
          <p className="font-semibold">{config.name}</p>
          <p className="text-sm text-meta">
            {config.org_type[0]?.toUpperCase()}{config.org_type.slice(1)} · {place}
          </p>
        </div>
        <nav aria-label="Main" className="grid gap-0.5 px-2">
          {items.map((i) => (
            <NavLink key={i.to} to={i.to} className={({ isActive }) => `flex min-h-11 items-center gap-3 rounded-control px-3 ${isActive ? 'bg-sunken font-semibold text-accent' : 'hover:bg-sunken'}`}>
              <i.icon size={20} strokeWidth={1.75} aria-hidden />
              {i.label}
              {i.to === '/alerts' && alerts.data && alerts.data.alerts.length > 0 && <span className="ml-auto text-sm text-meta">{alerts.data.alerts.length}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto border-t border-line px-4 py-3 text-sm">
          <p className="font-semibold">{me.display_name}</p>
          <Button kind="quiet" onClick={logout} className="mt-1 !px-0">
            <span className="inline-flex items-center gap-2">
              <LogOut size={16} strokeWidth={1.75} aria-hidden /> Log out
            </span>
          </Button>
          <div className="mt-2"><ThemeSwitch /></div>
        </div>
      </aside>
      <div className="min-w-0">
        {config.mode === 'simulation' && (
          <div className="bg-unk-bg px-4 py-1.5 text-center text-sm text-unk-fg">Simulation: all organisations are running on this computer</div>
        )}
        <header className="flex items-center justify-between border-b border-line px-4 py-1 md:justify-end">
          <p className="font-semibold md:hidden">{config.name}</p>
          <NetworkStatus />
        </header>
        <main className="mx-auto max-w-[1120px] px-4 py-6 pb-24 md:px-8 md:pb-6">
          <Outlet />
        </main>
        {more && (
          <div role="dialog" aria-label="More" className="fixed inset-x-0 bottom-14 z-10 grid gap-1 border-t border-line-strong bg-surface p-3 md:hidden" style={{ boxShadow: 'var(--shadow-float)' }}>
            {items.slice(4).map((i) => (
              <NavLink key={i.to} to={i.to} onClick={() => setMore(false)} className="flex min-h-11 items-center gap-3 rounded-control px-3 hover:bg-sunken">
                <i.icon size={20} strokeWidth={1.75} aria-hidden />
                {i.label}
              </NavLink>
            ))}
            <div className="border-t border-line px-3 pt-3"><ThemeSwitch /></div>
            <Button kind="quiet" onClick={logout} className="justify-self-start">
              <span className="inline-flex items-center gap-2"><LogOut size={16} strokeWidth={1.75} aria-hidden /> Log out</span>
            </Button>
          </div>
        )}
        <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-5 border-t border-line bg-surface md:hidden">
          {items.slice(0, 4).map((i) => (
            <NavLink key={i.to} to={i.to} onClick={() => setMore(false)} className={({ isActive }) => `flex min-h-14 flex-col items-center justify-center gap-0.5 text-[13px] ${isActive ? 'font-semibold text-accent' : ''}`}>
              <i.icon size={20} strokeWidth={1.75} aria-hidden />
              {i.label}
            </NavLink>
          ))}
          <button type="button" aria-expanded={more} onClick={() => setMore(!more)} className={`flex min-h-14 flex-col items-center justify-center gap-0.5 text-[13px] ${more ? 'font-semibold text-accent' : ''}`}>
            <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
            More
          </button>
        </nav>
      </div>
    </div>
  )
}
