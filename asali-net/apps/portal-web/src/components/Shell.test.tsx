import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Config, Me } from '../api/types'
import { Shell } from './Shell'

vi.mock('./NetworkStatus', () => ({ NetworkStatus: () => null }))

const config = (org_type: Config['org_type']): Config => ({ org_id: 'x', org_type, name: 'Test Org', city: 'Delhi', state: 'DL', mode: 'network', host_name: 'H', issuer_code: null, gs1_prefix: null, shop: null })
const me: Me = { username: 'staff', role: 'staff', display_name: 'Staff', org_id: 'x', org_type: 'pharma' }

function show(org: Config['org_type']) {
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><Shell config={config(org)} me={me} /></MemoryRouter></QueryClientProvider>)
  return screen.getAllByRole('navigation', { name: 'Main' }).at(-1)!
}

describe('phone navigation', () => {
  beforeEach(() => localStorage.clear())

  it('shows four items and a More button, and More holds the rest', () => {
    const bar = show('pharma')
    expect(within(bar).getAllByRole('link')).toHaveLength(4)
    fireEvent.click(within(bar).getByRole('button', { name: 'More' }))
    const sheet = screen.getByRole('dialog', { name: 'More' })
    for (const name of ['Documents', 'Activity', 'Network']) expect(within(sheet).getByRole('link', { name })).toBeTruthy()
    expect(within(sheet).getByRole('button', { name: 'Log out' })).toBeTruthy()
  })

  it('closes with Escape', () => {
    const bar = show('pharma')
    fireEvent.click(within(bar).getByRole('button', { name: 'More' }))
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog', { name: 'More' })).toBeNull()
  })

  it('lets the person choose light, dark or the system setting', () => {
    const bar = show('pharma')
    fireEvent.click(within(bar).getByRole('button', { name: 'More' }))
    const sheet = screen.getByRole('dialog', { name: 'More' })
    fireEvent.click(within(sheet).getByRole('radio', { name: 'Dark' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    fireEvent.click(within(sheet).getByRole('radio', { name: 'System' }))
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })
})
