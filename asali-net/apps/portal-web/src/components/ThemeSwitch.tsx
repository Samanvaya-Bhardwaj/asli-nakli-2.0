import { useState } from 'react'
import { readTheme, setTheme, type Theme } from '../lib/theme'

const CHOICES: { value: Theme; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]

export function ThemeSwitch() {
  const [theme, set] = useState<Theme>(readTheme)
  return (
    <div role="radiogroup" aria-label="Colour theme" className="inline-flex overflow-hidden rounded-control border border-line-strong text-sm">
      {CHOICES.map((c) => (
        <button key={c.value} type="button" role="radio" aria-checked={theme === c.value} onClick={() => { setTheme(c.value); set(c.value) }}
          className={`min-h-11 px-4 ${theme === c.value ? 'bg-sunken font-semibold' : ''}`}>
          {c.label}
        </button>
      ))}
    </div>
  )
}
