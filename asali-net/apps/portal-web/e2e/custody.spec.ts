import { expect, test, type Page } from '@playwright/test'
import { NODE, element, login, noAxeViolations, scanCodes, wedgeBurst } from './helpers'

interface Label { gtin: string; serial: string }

// One pack's whole life through the portals: made, dispatched, partly received, forwarded, sold, checked.
test('pharma to distributor to shop to consumer', async ({ browser }) => {
  const ctx = async (base: string) => { const c = await browser.newContext(); const p = await c.newPage(); await login(p, base); return p }

  // 1. The pharma makes 10 packs of a new batch and dispatches 5 of them to North Star, typing the codes.
  const pharma = await ctx(NODE.tarang)
  await pharma.goto(NODE.tarang + '/batches')
  const lots = async () => ((await (await pharma.request.get(`${NODE.tarang}/api/batches`)).json()).batches as { lot: string }[]).map((b) => b.lot)
  const before = await lots()
  await pharma.getByLabel('Product').selectOption({ index: 1 })
  await pharma.getByLabel('Manufacturing date').fill('2026-10-20')
  await pharma.getByLabel('Expiry date').fill('2028-10-31')
  await pharma.getByLabel('Planned quantity').fill('10')
  await pharma.getByRole('button', { name: 'Create batch' }).click()
  await expect.poll(async () => (await lots()).length).toBe(before.length + 1)
  const lot = (await lots()).find((l) => !before.includes(l)) as string
  await pharma.getByLabel(`Packs to make in ${lot}`).fill('10')
  await pharma.locator('tr', { hasText: lot }).getByRole('button', { name: 'Make packs' }).click()
  await expect(pharma.getByText('Packs made.')).toBeVisible()
  const labels = (await (await pharma.request.get(`${NODE.tarang}/api/batches/${lot}/labels`)).json()).labels as Label[]
  expect(labels).toHaveLength(10)
  const first5 = labels.slice(0, 5)
  await pharma.goto(NODE.tarang + '/dispatch')
  await pharma.getByText('North Star Distributors, Delhi').click()
  await pharma.getByRole('button', { name: 'Start dispatch' }).click()
  await scanCodes(pharma, first5.map((l) => element(l.gtin, l.serial)))
  await noAxeViolations(pharma, 'pharma-dispatch-session')
  await pharma.getByRole('button', { name: 'Record dispatch of 5' }).click()
  await expect(pharma.getByText('Recorded dispatch of 5 packs.')).toBeVisible()

  // 2. North Star receives 4 of them; the missing one is shown and noted.
  const north = await ctx(NODE['dist-north'])
  await north.goto(NODE['dist-north'] + '/receive')
  await north.getByRole('link', { name: 'Receive these packs' }).first().click()
  await scanCodes(north, first5.slice(0, 4).map((l) => element(l.gtin, l.serial)))
  await expect(north.getByText('4 of 5 packs scanned')).toBeVisible()
  await north.getByRole('button', { name: 'Record receipt of 4' }).click()
  await expect(north.getByText(/Received 4 packs\. 1 missing/)).toBeVisible()

  // 3. North Star sends 3 to Sharma Medicos, scanned as a fast burst from a keyboard-wedge scanner.
  const three = first5.slice(0, 3)
  await north.goto(NODE['dist-north'] + '/dispatch')
  await north.getByText('Sharma Medicos, Delhi').click()
  await north.getByRole('button', { name: 'Start dispatch' }).click()
  for (const l of three) {
    await north.locator('main').click({ position: { x: 5, y: 5 } })
    await wedgeBurst(north, element(l.gtin, l.serial))
  }
  await expect(north.getByText('3 packs scanned')).toBeVisible()
  await north.getByRole('button', { name: 'Record dispatch of 3' }).click()
  await expect(north.getByText('Recorded dispatch of 3 packs.')).toBeVisible()

  // 4. The shop receives them and sells one.
  const shop = await ctx(NODE['shop-delhi'])
  await shop.goto(NODE['shop-delhi'] + '/receive')
  await shop.getByRole('link', { name: 'Receive these packs' }).first().click()
  await scanCodes(shop, three.map((l) => element(l.gtin, l.serial)))
  await shop.getByRole('button', { name: 'Record receipt of 3' }).click()
  await expect(shop.getByText('Received 3 packs.')).toBeVisible()
  await sellOne(shop, three[0]!)

  // 5. A customer checks the sold pack: Genuine, with the custody chain.
  const consumer = await ctx2(browser, NODE['consumer-delhi'])
  await consumer.getByLabel('Code on the pack').fill(three[0]!.serial)
  await consumer.getByRole('button', { name: 'Check medicine' }).click()
  await expect(consumer.getByRole('status').filter({ hasText: 'Genuine' })).toBeVisible()
  await expect(consumer.getByText('Sold by Sharma Medicos').first()).toBeVisible()
})

async function sellOne(shop: Page, l: Label) {
  await shop.goto(NODE['shop-delhi'] + '/sell')
  await scanCodes(shop, [element(l.gtin, l.serial)])
  await shop.getByRole('textbox', { name: l.gtin, exact: true }).fill('125.50')
  await noAxeViolations(shop, 'shop-sell-session')
  await shop.getByRole('button', { name: 'Record sale of 1' }).click()
  await expect(shop.getByText(/Recorded sale B-/)).toBeVisible()
  await noAxeViolations(shop, 'shop-receipt')
}

async function ctx2(browser: import('@playwright/test').Browser, base: string) {
  const c = await browser.newContext()
  const p = await c.newPage()
  await p.goto(base + '/')
  return p
}
