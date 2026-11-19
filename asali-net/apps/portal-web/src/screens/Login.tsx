import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import type { Config } from '../api/types'
import { Button, Field, Input, ProblemMessage } from '../components/ui'

export function Login({ config }: { config: Config }) {
  const qc = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api('/api/login', { method: 'POST', json: { username, password } })
      await qc.invalidateQueries({ queryKey: ['me'] })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }
  return (
    <main className="mx-auto grid min-h-screen max-w-sm content-center gap-6 px-4 py-10">
      <div className="border-t-[3px] border-accent pt-4">
        <h1>{config.name}</h1>
        <p className="text-muted">
          {config.org_type[0]?.toUpperCase()}
          {config.org_type.slice(1)} · {config.city}
        </p>
      </div>
      {config.mode === 'simulation' && <p className="text-sm text-meta">Simulation: all organisations are running on this computer.</p>}
      <form onSubmit={submit} className="grid gap-4">
        <Field label="Username">
          <Input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </Field>
        <Field label="Password">
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
        </Field>
        <ProblemMessage error={error} />
        <Button kind="primary" type="submit" disabled={busy}>
          Log in
        </Button>
      </form>
    </main>
  )
}
