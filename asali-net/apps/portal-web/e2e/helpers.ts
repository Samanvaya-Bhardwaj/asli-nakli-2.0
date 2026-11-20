import AxeBuilder from '@axe-core/playwright'
import { expect, type Page } from '@playwright/test'
import { mkdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = fileURLToPath(new URL('.', import.meta.url))

const SIM = join(here, '..', '..', '..', 'infra', 'out', 'SIM')
export const secrets = JSON.parse(readFileSync(join(SIM, 'secrets.json'), 'utf8')) as { staff_password: string }
export const scenarios = JSON.parse(readFileSync(join(SIM, 'scenarios.json'), 'utf8')) as Record<string, { raw: string; serial: string; true_serial?: string }>
export const NODE = {
  tarang: 'http://127.0.0.1:8301', 'dist-north': 'http://127.0.0.1:8101', 'dist-west': 'http://127.0.0.1:8102',
  'shop-delhi': 'http://127.0.0.1:8201', 'consumer-delhi': 'http://127.0.0.1:8402', 'consumer-mumbai': 'http://127.0.0.1:8403',
} as const
const SHOTS = join(here, '..', '..', '..', 'docs', 'evidence', 'ui', 'e2e')

export async function login(page: Page, base: string) {
  await page.goto(base + '/')
  await page.getByLabel('Username').fill('staff')
  await page.getByLabel('Password').fill(secrets.staff_password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('navigation', { name: 'Main' }).first()).toBeVisible()
}

export async function noAxeViolations(page: Page, name: string) {
  await page.waitForTimeout(300) // let the verdict's short fade-in finish, so the screenshot and the contrast check see the final colours
  mkdirSync(SHOTS, { recursive: true })
  await page.screenshot({ path: join(SHOTS, `${name}.png`), fullPage: true })
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()
  const summary = results.violations.map((v) => `${v.id} (${v.nodes.length}): ${v.nodes[0]?.html.slice(0, 260)} | ${JSON.stringify(v.nodes[0]?.any[0]?.data ?? {}).slice(0, 200)}`)
  expect(summary, `accessibility problems on ${name}`).toEqual([])
}

export async function scanCodes(page: Page, codes: string[]) {
  const box = page.getByLabel('Scan or type a code')
  for (const raw of codes) {
    await box.fill(raw)
    await box.press('Enter')
    await expect(page.getByRole('list').first()).toContainText(/Read|Corrected|Rejected|Duplicate|Choose/)
  }
}

export const element = (gtin: string, serial: string) => `(01)${gtin}(21)${serial}`

// A keyboard-wedge scanner delivers a whole code within a few milliseconds and ends with Enter. Driving the keyboard
// from outside the browser is slower than that on a busy computer, so the burst is dispatched inside the page.
export async function wedgeBurst(page: Page, text: string) {
  await page.evaluate((t) => {
    for (const ch of t) window.dispatchEvent(new KeyboardEvent('keydown', { key: ch, bubbles: true, cancelable: true }))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true }))
  }, text)
}
