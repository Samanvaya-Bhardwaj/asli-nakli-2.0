import { expect, test } from '@playwright/test'
import { NODE, login, noAxeViolations } from './helpers'

test.use({ viewport: { width: 360, height: 740 } })

test('on a phone the rest of the menu is under More, and the theme can be changed', async ({ page }) => {
  await login(page, NODE['shop-delhi'])
  const bar = page.getByRole('navigation', { name: 'Main' })
  await expect(bar.getByRole('link')).toHaveCount(4)
  await bar.getByRole('button', { name: 'More' }).click()
  const sheet = page.getByRole('dialog', { name: 'More' })
  await expect(sheet.getByRole('link', { name: 'Network' })).toBeVisible()
  await sheet.getByRole('radio', { name: 'Dark' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await noAxeViolations(page, 'phone-more-dark')
  await sheet.getByRole('link', { name: 'Network' }).click()
  await expect(page.getByRole('dialog', { name: 'More' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Network' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await noAxeViolations(page, 'phone-network-dark')
})

test('the consumer page can be set to dark and keeps passing the accessibility check', async ({ page }) => {
  await page.goto(NODE['consumer-delhi'] + '/')
  await page.getByRole('radio', { name: 'Dark' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await noAxeViolations(page, 'consumer-home-dark')
})
