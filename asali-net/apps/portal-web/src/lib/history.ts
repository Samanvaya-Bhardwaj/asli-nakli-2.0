import type { VerifyResult } from '../api/types'

const KEY = 'asali.history'
export interface Remembered { id: string; at: string; word: string; verdict: string; text: string; result: VerifyResult }

export function remember(result: VerifyResult): string {
  const id = `${Date.now().toString(36)}-${result.pack.serial.slice(-4)}`
  try {
    const all: Remembered[] = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    all.unshift({ id, at: result.checked_at, word: result.word, verdict: result.verdict, text: result.pack.product ? `${result.pack.product.brand} ${result.pack.product.strength}` : result.pack.serial, result })
    localStorage.setItem(KEY, JSON.stringify(all.slice(0, 20)))
  } catch {
    /* storage blocked: the check still works, it is just not remembered */
  }
  return id
}
export function recall(): Remembered[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as Remembered[]
  } catch {
    return []
  }
}

