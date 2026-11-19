import { useEffect, useRef } from 'react'

// A keyboard-wedge scanner types a whole code in a few milliseconds and ends with Enter or Tab (PLAN.md 10.3).
// A burst is at least 8 characters, at most 35 ms apart, ending in Enter or Tab, or followed by 80 ms of quiet.
export const BURST_MIN = 8
export const BURST_GAP_MS = 35
export const BURST_QUIET_MS = 80
const ALLOWED = /^[0-9A-Za-z()\-\x1d/:?=&.]+$/ // eslint-disable-line no-control-regex -- GS (0x1d) is part of a scan

export function layoutLooksWrong(raw: string): boolean {
  return !ALLOWED.test(raw)
}

export function useScannerBursts(onBurst: (raw: string) => void, enabled = true): void {
  const handler = useRef(onBurst)
  useEffect(() => {
    handler.current = onBurst
  }, [onBurst])

  useEffect(() => {
    if (!enabled) return
    let buf = ''
    let last = 0
    let quiet: ReturnType<typeof setTimeout> | undefined
    const fire = () => {
      if (buf.length >= BURST_MIN) handler.current(buf)
      buf = ''
    }
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if ((target instanceof Element && target.closest('[data-scan-input]')) || e.ctrlKey || e.metaKey || e.altKey) return
      clearTimeout(quiet)
      if (e.key.length === 1) {
        const now = performance.now()
        buf = now - last > BURST_GAP_MS ? e.key : buf + e.key
        last = now
        quiet = setTimeout(fire, BURST_QUIET_MS)
      } else if ((e.key === 'Enter' || e.key === 'Tab') && buf.length >= BURST_MIN) {
        e.preventDefault()
        fire()
      } else {
        buf = ''
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
      clearTimeout(quiet)
    }
  }, [enabled])
}
