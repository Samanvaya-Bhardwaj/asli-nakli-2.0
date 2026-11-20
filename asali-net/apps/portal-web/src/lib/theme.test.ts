import { beforeEach, describe, expect, it } from 'vitest'
import { applyTheme, readTheme, setTheme } from './theme'

describe('theme', () => {
  beforeEach(() => {
    localStorage.clear()
    delete document.documentElement.dataset.theme
  })

  it('follows the system until a choice is made', () => {
    expect(readTheme()).toBe('system')
    applyTheme()
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })

  it('remembers light and dark and applies them', () => {
    setTheme('dark')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(readTheme()).toBe('dark')
    setTheme('light')
    expect(document.documentElement.dataset.theme).toBe('light')
  })

  it('going back to the system setting removes the override', () => {
    setTheme('dark')
    setTheme('system')
    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(readTheme()).toBe('system')
  })

  it('ignores a stored value it does not know', () => {
    localStorage.setItem('asali-theme', 'sepia')
    expect(readTheme()).toBe('system')
  })

  it('still works when storage is blocked', () => {
    const real = Storage.prototype.setItem
    Storage.prototype.setItem = () => { throw new Error('blocked') }
    try {
      setTheme('dark')
      expect(document.documentElement.dataset.theme).toBe('dark')
    } finally {
      Storage.prototype.setItem = real
    }
  })
})
