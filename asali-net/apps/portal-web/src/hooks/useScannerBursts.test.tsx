import { render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { layoutLooksWrong, useScannerBursts } from './useScannerBursts'

function Probe({ onBurst }: { onBurst: (raw: string) => void }) {
  useScannerBursts(onBurst)
  return <button>elsewhere</button>
}

function type(text: string, gapMs: number, key?: string) {
  let t = 0
  for (const ch of text) {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: ch, bubbles: true }))
    t += gapMs
    vi.advanceTimersByTime(gapMs)
  }
  if (key) window.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
  return t
}

describe('scanner bursts', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('sends a fast run of characters ending in Enter', () => {
    const onBurst = vi.fn()
    render(<Probe onBurst={onBurst} />)
    type('TPM9S346Q37', 5, 'Enter')
    expect(onBurst).toHaveBeenCalledWith('TPM9S346Q37')
  })

  it('sends a fast run that simply stops (80 ms of quiet)', () => {
    const onBurst = vi.fn()
    render(<Probe onBurst={onBurst} />)
    type('TPM9S346Q37', 5)
    vi.advanceTimersByTime(100)
    expect(onBurst).toHaveBeenCalledWith('TPM9S346Q37')
  })

  it('ignores a person typing slowly and runs shorter than 8 characters', () => {
    const onBurst = vi.fn()
    render(<Probe onBurst={onBurst} />)
    type('TPM9S346Q37', 200, 'Enter')
    type('ABC123', 5, 'Enter')
    vi.advanceTimersByTime(500)
    expect(onBurst).not.toHaveBeenCalled()
  })

  it('does not take keys typed into the scan box itself', () => {
    const onBurst = vi.fn()
    render(
      <>
        <Probe onBurst={onBurst} />
        <input data-scan-input aria-label="scan" />
      </>,
    )
    const input = document.querySelector('input') as HTMLInputElement
    for (const ch of 'TPM9S346Q37') input.dispatchEvent(new KeyboardEvent('keydown', { key: ch, bubbles: true }))
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    vi.advanceTimersByTime(200)
    expect(onBurst).not.toHaveBeenCalled()
  })

  it('flags characters a different keyboard layout would produce', () => {
    expect(layoutLooksWrong('(01)08901001000124(21)TPM9S346Q37')).toBe(false)
    expect(layoutLooksWrong('ТРМ9S346Q37')).toBe(true) // Cyrillic lookalikes
    expect(layoutLooksWrong('TPM9 S346')).toBe(true)
  })
})
