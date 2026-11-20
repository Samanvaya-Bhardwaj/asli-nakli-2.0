import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Ellipsis, LogOut } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router'
import { api } from '../api/client'
import type { Config, Me } from '../api/types'
import { Brand } from './Mark'
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
    <div className="min-h-screen md:grid md:grid-cols-[248px_1fr]">
      <aside className="hidden bg-surface shadow-[inset_-1px_0_0_var(--border)] md:sticky md:top-0 md:flex md:h-screen md:flex-col">
        <div className="px-5 pt-5">
          <Brand />
        </div>
        <div className="px-5 pb-4 pt-5">
          <p className="text-[17px] font-semibold leading-snug tracking-[-0.015em]">{config.name}</p>
          <p className="mt-0.5 text-sm text-meta">
            {config.org_type[0]?.toUpperCase()}{config.org_type.slice(1)} · {place}
          </p>
        </div>
        <nav aria-label="Main" className="grid gap-1 px-3">
          {items.map((i) => (
            <NavLink key={i.to} to={i.to} className={({ isActive }) => `group flex min-h-11 items-center gap-3 rounded-full px-4 text-[15px] transition-colors duration-150 ${isActive ? 'bg-sunken font-semibold text-ink shadow-[inset_0_0_0_1px_var(--border-strong)] [&_svg]:text-accent-ink' : 'text-muted hover:bg-surface-2 hover:text-ink'}`}>
              <i.icon size={19} strokeWidth={1.75} aria-hidden />
              {i.label}
              {i.to === '/alerts' && alerts.data && alerts.data.alerts.length > 0 && <span className="ml-auto rounded-full bg-warn-bg px-2 text-[13px] font-semibold text-warn-fg">{alerts.data.alerts.length}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto grid gap-3 px-5 py-4 text-sm shadow-[inset_0_1px_0_var(--border)]">
          <div>
            <p className="font-semibold">{me.display_name}</p>
            <Button kind="quiet" onClick={logout} className="mt-0.5 !px-0 text-sm text-muted hover:!bg-transparent hover:text-ink">
              <span className="inline-flex items-center gap-2">
                <LogOut size={16} strokeWidth={1.75} aria-hidden /> Log out
              </span>
            </Button>
          </div>
          <ThemeSwitch />
        </div>
      </aside>
      <div className="min-w-0">
        {config.mode === 'simulation' && (
          <div className="hatch bg-unk-bg px-4 py-1.5 text-center text-sm font-medium text-unk-fg">Simulation: all organisations are running on this computer</div>
        )}
        <header className="sticky top-0 z-10 flex min-h-16 items-center justify-between gap-3 bg-[var(--nav-bg)] px-4 shadow-[inset_0_-1px_0_var(--border)] backdrop-blur-xl md:justify-end md:px-8">
          <p className="min-w-0 truncate md:hidden"><Brand compact>{config.name}</Brand></p>
          <NetworkStatus />
        </header>
        <main className="mx-auto max-w-[1180px] px-4 py-8 pb-28 md:px-10 md:pb-12">
          <Outlet />
        </main>
        {more && (
          <div role="dialog" aria-label="More" className="fixed inset-x-0 bottom-16 z-10 mx-2 grid gap-1 rounded-panel bg-surface p-3 shadow-pop md:hidden">
            {items.slice(4).map((i) => (
              <NavLink key={i.to} to={i.to} onClick={() => setMore(false)} className="flex min-h-11 items-center gap-3 rounded-full px-4 hover:bg-sunken">
                <i.icon size={20} strokeWidth={1.75} aria-hidden />
                {i.label}
              </NavLink>
            ))}
            <div className="mt-1 px-1 pt-3 shadow-[inset_0_1px_0_var(--border)]"><ThemeSwitch /></div>
            <Button kind="quiet" onClick={logout} className="justify-self-start">
              <span className="inline-flex items-center gap-2"><LogOut size={16} strokeWidth={1.75} aria-hidden /> Log out</span>
            </Button>
          </div>
        )}
        <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-5 bg-[var(--nav-bg)] px-1 shadow-[inset_0_1px_0_var(--border)] backdrop-blur-xl md:hidden">
          {items.slice(0, 4).map((i) => (
            <NavLink key={i.to} to={i.to} onClick={() => setMore(false)} className={({ isActive }) => `flex min-h-16 flex-col items-center justify-center gap-1 text-[13px] ${isActive ? 'font-semibold text-accent-ink' : 'text-muted'}`}>
              <i.icon size={20} strokeWidth={1.75} aria-hidden />
              {i.label}
            </NavLink>
          ))}
          <button type="button" aria-expanded={more} onClick={() => setMore(!more)} className={`flex min-h-16 flex-col items-center justify-center gap-1 text-[13px] ${more ? 'font-semibold text-accent-ink' : 'text-muted'}`}>
            <Ellipsis size={20} strokeWidth={1.75} aria-hidden />
            More
          </button>
        </nav>
      </div>
    </div>
  )
}
