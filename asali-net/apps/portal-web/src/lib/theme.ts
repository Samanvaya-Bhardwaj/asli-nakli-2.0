export type Theme = 'system' | 'light' | 'dark'
const KEY = 'asali-theme'

export function readTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

// "system" leaves data-theme off, so tokens.css follows prefers-color-scheme.
export function applyTheme(theme: Theme = readTheme()) {
  if (theme === 'system') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = theme
}

export function setTheme(theme: Theme) {
  try {
    if (theme === 'system') localStorage.removeItem(KEY)
    else localStorage.setItem(KEY, theme)
  } catch {
    // Storage can be blocked; the choice then lasts until the page is closed.
  }
  applyTheme(theme)
}
