import { expect, test } from '@playwright/test'
import { NODE, noAxeViolations, scenarios } from './helpers'

test.describe('consumer portal', () => {
  test('a normal pack is Genuine, with each organisation and its computer named', async ({ page }) => {
    await page.goto(NODE['consumer-delhi'] + '/')
    await noAxeViolations(page, 'consumer-home')
    await page.getByLabel('Code on the pack').fill(scenarios.S1!.raw)
    await page.getByRole('button', { name: 'Check medicine' }).click()
    const verdict = page.getByRole('status').filter({ hasText: 'Genuine' })
    await expect(verdict).toBeVisible()
    await expect(page.getByText('Simulation').first()).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Where this pack has been' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Computer (simulation)' })).toBeVisible()
    const hosts = await page.locator('td.font-mono').allTextContents()
    expect(new Set(hosts.filter(Boolean)).size).toBeGreaterThanOrEqual(1)
    await noAxeViolations(page, 'consumer-genuine')
  })

  test('a misread code asks for confirmation, then gives the same result', async ({ page }) => {
    await page.goto(NODE['consumer-delhi'] + '/')
    await page.getByLabel('Code on the pack').fill(scenarios.S9!.raw)
    await page.getByRole('button', { name: 'Check medicine' }).click()
    await expect(page.getByText('Does your pack show')).toBeVisible()
    await noAxeViolations(page, 'consumer-confirm')
    await page.getByRole('button', { name: 'Yes, check it' }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Genuine' })).toBeVisible()
  })

  test('a copied code is Do not use and the customer report is shown against the records', async ({ page }) => {
    await page.goto(NODE['consumer-delhi'] + '/')
    await page.getByLabel('Code on the pack').fill(scenarios.S3!.raw)
    await page.getByRole('button', { name: 'Check medicine' }).click()
    const verdict = page.getByRole('status').filter({ hasText: 'Do not use' })
    await expect(verdict).toBeVisible()
    await expect(verdict).toContainText('Do not take this medicine')
    await expect(page.getByText('Reported by a customer, not verified').first()).toBeVisible()
    await noAxeViolations(page, 'consumer-do-not-use')
  })

  test('the result shows the context each organisation found through its own keys', async ({ page }) => {
    await page.goto(NODE['consumer-delhi'] + '/')
    await page.getByLabel('Code on the pack').fill(scenarios.S5!.raw)
    await page.getByRole('button', { name: 'Check medicine' }).click()
    await expect(page.getByRole('heading', { name: 'Context found across organisations' })).toBeVisible()
    await expect(page.getByText(/organisations asked, \d+ found context/)).toBeVisible()
    await page.getByText('How each organisation found it').click()
    await expect(page.getByText(/foreign key|\(.*\) -> .*\(.*\)/).first()).toBeVisible()
    await noAxeViolations(page, 'consumer-context')
  })

  test('a notice that exists only as text makes a batch Do not use', async ({ page }) => {
    await page.goto(NODE['consumer-delhi'] + '/')
    await page.getByLabel('Code on the pack').fill(scenarios.S5!.raw)
    await page.getByRole('button', { name: 'Check medicine' }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Do not use' })).toBeVisible()
    await expect(page.getByText('not of standard quality').first()).toBeVisible()
  })

  test('the report page works on a phone-sized screen', async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 740 })
    await page.goto(NODE['consumer-delhi'] + '/report')
    await expect(page.getByRole('heading', { name: 'Report a problem' })).toBeVisible()
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
    expect(overflow).toBe(false)
    await noAxeViolations(page, 'consumer-report-360')
  })
})
