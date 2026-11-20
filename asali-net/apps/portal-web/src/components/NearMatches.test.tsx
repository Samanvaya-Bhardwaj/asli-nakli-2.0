import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Similar } from '../api/generated'
import { NearMatches } from './NearMatches'

afterEach(cleanup)

const base: Similar = {
  read: { raw: 'KS21P05SSBS', serial: 'KS21P05SSBS', lot: 'K/26/0001', expiry: null },
  matches: [
    { serial: 'KS21P0SS5BS', gtin: '08901003000111', org_id: 'kesar', cost: 0.3, edits: ['pos7 5->S'], lot: 'K/26/0001', expiry: '2027-03-31', product: 'Glargikes 100 IU/ml', fits_label: true },
    { serial: 'KS21P05SSB7', gtin: null, org_id: 'kesar', cost: 1.0, edits: ['pos11 S->7'], lot: 'K/26/0002', expiry: null, product: null, fits_label: false },
  ],
  seen_as: [{ raw_input: 'KS21P05SSBS', serial_read: 'KS21P05SSBS', cost: 0.3, edits: ['pos7 5->S'], city: 'Delhi', at: '2026-11-11T10:00:00+05:30', portal: 'consumer-delhi' }],
}

describe('near matches', () => {
  it('lists each issued code close to the reading, cheapest first, with what changed', () => {
    render(<NearMatches data={base} />)
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]!).getByLabelText('Copy code KS21P0SS5BS')).toBeTruthy()
    expect(within(rows[0]!).getByText('pos7 5->S')).toBeTruthy()
    expect(within(rows[0]!).getByText('Glargikes 100 IU/ml')).toBeTruthy()
  })

  it('says in words whether the lot printed on the label fits each code', () => {
    render(<NearMatches data={base} />)
    expect(screen.getByText('Lot fits the label')).toBeTruthy()
    expect(screen.getByText('Lot does not fit the label')).toBeTruthy()
  })

  it('shows the readings recorded against a code as the other direction', () => {
    render(<NearMatches data={base} />)
    expect(screen.getByRole('heading', { name: 'Readings recorded for this code' })).toBeTruthy()
    expect(screen.getByText('Delhi')).toBeTruthy()
  })

  it('says plainly when nothing issued is close', () => {
    render(<NearMatches data={{ ...base, matches: [], seen_as: [] }} />)
    expect(screen.getByText(/No issued code is close to this reading/)).toBeTruthy()
  })

  it('does not claim the matches are corrections', () => {
    render(<NearMatches data={base} />)
    expect(screen.getByText(/Nothing here changes a record/)).toBeTruthy()
  })
})
