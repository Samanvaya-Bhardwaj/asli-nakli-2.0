import { expect, test } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { NODE, noAxeViolations, scenarios } from './helpers'

const ROOT = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..')
const control = (fn: 'stop_org' | 'start_org') =>
  execFileSync(join(ROOT, '.venv', 'Scripts', 'python.exe'), ['-c', `import sys; sys.path.insert(0, 'infra/scripts'); import sim_control; sim_control.${fn}('dist-west')`], { cwd: ROOT })

// A computer on the pack's route is switched off: the portal must say it cannot check, name the computer, and not guess.
test('a stopped distributor makes the result Cannot check, and it recovers when it is back', async ({ page }) => {
  test.setTimeout(240_000)
  control('stop_org')
  try {
    await page.goto(NODE['consumer-delhi'] + '/')
    await page.getByLabel('Code on the pack').fill(scenarios.S8!.raw)
    await page.getByRole('button', { name: 'Check medicine' }).click()
    const verdict = page.getByRole('status').filter({ hasText: 'Cannot check' })
    await expect(verdict).toBeVisible({ timeout: 60_000 })
    await expect(verdict).toContainText('Western Medilink did not answer')
    await noAxeViolations(page, 'consumer-cannot-check')
  } finally {
    control('start_org')
  }
  await page.goto(NODE['consumer-delhi'] + '/')
  await page.getByLabel('Code on the pack').fill(scenarios.S8!.raw)
  await page.getByRole('button', { name: 'Check medicine' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Cannot check' })).toHaveCount(0, { timeout: 60_000 })
  await expect(page.getByRole('status').first()).toBeVisible()
})
