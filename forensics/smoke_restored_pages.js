#!/usr/bin/env node
// Browser smoke for the restored NOOR frontend. Requires a local Chromium and
// either a resolvable puppeteer package or the global Codex installation.

const { resolve } = require('path')

let puppeteer
try {
  puppeteer = require('puppeteer')
} catch {
  puppeteer = require('/home/kinax/.npm-global/lib/node_modules/puppeteer')
}

const CHROMIUM_CANDIDATES = [
  process.env.CHROMIUM_PATH,
  '/usr/bin/chromium',
  '/usr/bin/google-chrome',
].filter(Boolean)

async function main() {
  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: CHROMIUM_CANDIDATES[0],
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  })
  const page = await browser.newPage()
  page.setDefaultTimeout(30000)

  const errors = []
  const bad = []
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`)
  })
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
  page.on('response', (response) => {
    if (response.status() >= 400) bad.push(`${response.status()} ${response.url()}`)
  })

  const routes = [
    '/',
    '/library/3',
    '/jobs',
    '/history',
    '/settings',
    '/files/actors',
    '/actors/4201',
    '/plugins/javdb',
    '/plugins/av-recommend',
    '/plugins/subscription-core',
    '/plugins/qbittorrent',
    '/search/resources',
  ]

  for (const route of routes) {
    try {
      await page.goto(`http://127.0.0.1:5173${route}`, {
        waitUntil: 'domcontentloaded',
        timeout: 30000,
      })
      await new Promise((done) => setTimeout(done, 2500))
      console.log(`OK ${route} -> ${page.url()}`)
    } catch (error) {
      errors.push(`${route} navigation: ${error.message}`)
    }
  }

  try {
    await page.goto('http://127.0.0.1:5173/plugins/javdb', {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    })
    await new Promise((done) => setTimeout(done, 2000))
    await page.evaluate(() => {
      const target = [...document.querySelectorAll('button, a, [role="tab"]')].find((element) =>
        /演员/.test(element.textContent || '') && !/演员榜/.test(element.textContent || ''),
      )
      target?.click()
    })
    await new Promise((done) => setTimeout(done, 2500))
    if (!page.url().includes('/actors')) errors.push('javdb actor tab did not route to /actors')
  } catch (error) {
    errors.push(`javdb actor tab: ${error.message}`)
  }

  try {
    await page.goto('http://127.0.0.1:5173/library/3', {
      waitUntil: 'domcontentloaded',
      timeout: 30000,
    })
    await new Promise((done) => setTimeout(done, 4000))
    const cards = await page.$$('.media-card, [class*="media-card"], .library-grid > *')
    if (cards.length) {
      await cards[0].click()
      await new Promise((done) => setTimeout(done, 3000))
      const text = await page.evaluate(() => document.body.innerText)
      if (!/基本信息|文件|演员|预览/.test(text)) errors.push('media detail panel did not open')
    }
  } catch (error) {
    errors.push(`media detail: ${error.message}`)
  }

  console.log(`HTTP_ERRORS ${JSON.stringify(bad.slice(0, 30))}`)
  console.log(`CONSOLE_ERRORS ${JSON.stringify(errors.slice(0, 40))}`)
  await browser.close()
  process.exit(bad.length || errors.length ? 1 : 0)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
