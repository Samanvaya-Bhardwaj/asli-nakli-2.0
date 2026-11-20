import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { ContextBlock, ContextDocHit } from '../api/types'
import { ContextSection } from './ContextSection'

const block: ContextBlock = {
  method: 'm', anchors: [], organisations_asked: ['medivra', 'dist-north', 'regulator'], organisations_contributing: ['medivra', 'dist-north'], distinct_terms: 2,
  question_words: ['recall'],
  terms: [
    { term: 'molecule=amlodipine', key: 'k1', kind: 'categorical', score: 1.4, organisations: ['medivra'], local_scores: { medivra: 1 }, query_match: true,
      why_relevant: ['reached through 1 foreign key join(s): lots(sku) -> skus(_id)', "matches the question's words"],
      provenance: [{ organisation: 'medivra', table: 'skus', column: 'molecule', step: 1, relationship_path: ['lots(sku) -> skus(_id)'], weight: 1 }] },
    { term: 'North Star Distributors', key: 'k2', kind: 'text', score: 0.9, organisations: ['dist-north', 'medivra'], local_scores: {}, query_match: false,
      why_relevant: ['found independently by 2 organisations (dist-north, medivra)'], provenance: [] },
  ],
  organisations: [
    { org_id: 'medivra', name: 'Medivra Labs', status: 'answered', reason: '', explored_tables: ['lots', 'skus'], joins: ['lots(sku) -> skus(_id)'], stop_reason: 'no unexplored neighbouring table', terms: 15, engine: 'mongo' },
    { org_id: 'dist-north', name: 'North Star Distributors', status: 'answered', reason: '', explored_tables: ['receipt_items', 'receipts'], joins: ['receipt_items(receipt_id) -> receipts(receipt_id)'], stop_reason: 'x', terms: 9, engine: 'postgres' },
    { org_id: 'regulator', name: 'Drug Control', status: 'unreachable', reason: 'no answer in time', explored_tables: [], joins: [], stop_reason: '', terms: 0, engine: null },
  ],
}
const doc: ContextDocHit = {
  doc_id: 'medivra:d1', org_id: 'medivra', org_name: 'Medivra Labs', doc_type: 'coa', kind: 'operational', title: 'Certificate of analysis', created_at: '2026-11-16T10:00:00+00:00',
  snippet: { text: 'Assay 99.8 percent for amlodipine' }, linked_to: [], claims: [], issue_labels: [], label: 'Record kept by an organisation on the route', matched_terms: ['amlodipine', 'medivra'], context_score: 0.8, found_by: 'context',
}

describe('context section', () => {
  afterEach(cleanup)
  it('lists the strongest terms with where they were found and why they matter', () => {
    render(<ContextSection context={block} related={[doc]} />)
    expect(screen.getByRole('heading', { name: 'Context found across organisations' })).toBeTruthy()
    const item = screen.getByText('molecule=amlodipine').closest('li')!
    expect(within(item).getByText(/skus\.molecule/)).toBeTruthy()
    expect(within(item).getByText(/foreign key join/)).toBeTruthy()
  })

  it('says how many organisations were asked and names the ones that did not answer', () => {
    render(<ContextSection context={block} related={[]} />)
    expect(screen.getByText(/3 organisations asked, 2 found context/)).toBeTruthy()
    expect(screen.getByText(/Drug Control did not answer/)).toBeTruthy()
  })

  it('shows, per organisation, the tables it explored and the keys it followed', () => {
    render(<ContextSection context={block} related={[]} />)
    const details = screen.getByText('How each organisation found it').closest('details')!
    expect(within(details).getByText(/lots, skus/)).toBeTruthy()
    expect(within(details).getByText(/receipt_items\(receipt_id\) -> receipts\(receipt_id\)/)).toBeTruthy()
  })

  it('shows related reading with the words that matched, and says it does not change the result', () => {
    render(<ContextSection context={block} related={[doc]} />)
    expect(screen.getByRole('heading', { name: 'Related documents found through the context' })).toBeTruthy()
    expect(screen.getByText(/amlodipine, medivra/)).toBeTruthy()
    expect(screen.getByText(/does not change the result/i)).toBeTruthy()
  })

  it('says so plainly when no organisation found any context', () => {
    render(<ContextSection context={{ ...block, terms: [], organisations_contributing: [] }} related={[]} />)
    expect(screen.getByText(/No organisation found context for this pack/)).toBeTruthy()
  })

  it('renders nothing when the result carries no context at all', () => {
    const { container } = render(<ContextSection context={null} related={[]} />)
    expect(container.firstChild).toBeNull()
  })
})
