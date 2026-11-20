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
    <div role="radiogroup" aria-label="Colour theme" className="inline-flex w-fit gap-1 rounded-full bg-inset p-1 text-sm shadow-[inset_0_0_0_1px_var(--border)]">
      {CHOICES.map((c) => (
        <button key={c.value} type="button" role="radio" aria-checked={theme === c.value} onClick={() => { setTheme(c.value); set(c.value) }}
          className={`min-h-11 rounded-full px-4 transition-colors duration-150 ${theme === c.value ? 'bg-sunken font-semibold text-ink shadow-[inset_0_0_0_1px_var(--border-strong)]' : 'text-muted hover:bg-surface-2 hover:text-ink'}`}>
          {c.label}
        </button>
      ))}
    </div>
  )
}
