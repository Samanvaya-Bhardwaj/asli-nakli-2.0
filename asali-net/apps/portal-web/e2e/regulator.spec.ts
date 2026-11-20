import { expect, test } from '@playwright/test'
import { NODE, login, noAxeViolations, scenarios } from './helpers'

const REGULATOR = 'http://127.0.0.1:8401'

test.describe('regulator portal', () => {
  test('traces a copied pack across every organisation that handled it', async ({ page }) => {
    await login(page, REGULATOR)
    await page.getByRole('link', { name: 'Investigate' }).first().click()
    await page.getByLabel('Code of the pack').fill(scenarios.S3!.raw)
    await page.getByRole('button', { name: 'Trace pack' }).click()
    await expect(page.getByRole('status').filter({ hasText: 'Do not use' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Where this pack has been' })).toBeVisible()
    await noAxeViolations(page, 'regulator-investigate')
  })

  test('complaints are grouped by batch and the unusual ones are marked', async ({ page }) => {
    await login(page, REGULATOR)
    await page.getByRole('link', { name: 'Complaints' }).first().click()
    await expect(page.getByText(/complaints are linked to a batch/)).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Batch status' })).toBeVisible()
    await noAxeViolations(page, 'regulator-complaints')
  })

  test('an alert issued by the regulator appears in a shop in that state', async ({ browser }) => {
    const reg = await (await browser.newContext()).newPage()
    await login(reg, REGULATOR)
    await reg.getByRole('link', { name: 'Alerts' }).first().click()
    const reason = `Browser test ${Date.now()}: not of standard quality`
    await reg.getByLabel('Product number').fill('08901001999999') // a product number no real pack carries
    await reg.getByLabel('Maker (organisation id)').fill('tarang')
    await reg.getByLabel('Reason').fill(reason)
    await reg.getByLabel('States').fill('DL')
    await reg.getByRole('button', { name: 'Issue alert' }).click()
    await expect(reg.getByText('Alert issued.')).toBeVisible()
    await noAxeViolations(reg, 'regulator-alerts')

    const shop = await (await browser.newContext()).newPage()
    await login(shop, NODE['shop-delhi'])
    await shop.getByRole('link', { name: 'Alerts' }).first().click()
    await expect(shop.getByText(reason)).toBeVisible()
    await noAxeViolations(shop, 'shop-alerts')
  })

  test('licences can be recorded and listed', async ({ page }) => {
    await login(page, REGULATOR)
    await page.getByRole('link', { name: 'Licences' }).first().click()
    const no = `KA-RT-${Date.now()}`
    await page.getByLabel('Organisation id').fill('shop-bengaluru')
    await page.getByLabel('Licence number').fill(no)
    await page.getByLabel('Valid from').fill('2026-01-01')
    await page.getByLabel('Valid until').fill('2030-12-31')
    await page.getByRole('button', { name: 'Save licence' }).click()
    await expect(page.getByRole('row', { name: new RegExp(no) })).toBeVisible()
    await noAxeViolations(page, 'regulator-licences')
  })
})
