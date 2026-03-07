import { test, expect } from '@playwright/test'

test.describe('Dashboard Smoke Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('page loads with correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/AI Co-Host/)
  })

  test('navigation bar is visible with status indicators', async ({ page }) => {
    await expect(page.locator('nav')).toBeVisible()
    await expect(page.locator('text=AI Co-Host Dashboard')).toBeVisible()
    await expect(page.locator('#connection-indicator')).toBeVisible()
    await expect(page.locator('#health-indicator')).toBeVisible()
    await expect(page.locator('#mode-indicator')).toBeVisible()
  })

  test('all four left-side panels are visible', async ({ page }) => {
    await expect(page.locator('text=Control Panel').first()).toBeVisible()
    await expect(page.locator('text=Ask ChatGPT').first()).toBeVisible()
    await expect(page.locator('text=Configuration').first()).toBeVisible()
    await expect(page.locator('text=Context Summary').first()).toBeVisible()
  })

  test('both right-side panels are visible', async ({ page }) => {
    await expect(page.locator('text=Live Conversation').first()).toBeVisible()
    await expect(page.locator('text=AI Insights').first()).toBeVisible()
  })

  test('panel layout order is correct (2x2 + 2 columns)', async ({ page }) => {
    // Control Panel should be top-left, Ask ChatGPT top-right
    const controlPanel = page.locator('text=Control Panel').first()
    const askChatGPT = page.locator('h3:has-text("Ask ChatGPT")').first()
    const config = page.locator('text=Configuration').first()
    const contextSummary = page.locator('text=Context Summary').first()

    const cpBox = await controlPanel.boundingBox()
    const chatBox = await askChatGPT.boundingBox()
    const cfgBox = await config.boundingBox()
    const csBox = await contextSummary.boundingBox()

    // Control Panel left of Ask ChatGPT (same row)
    expect(cpBox!.x).toBeLessThan(chatBox!.x)
    expect(Math.abs(cpBox!.y - chatBox!.y)).toBeLessThan(50)

    // Configuration below Control Panel
    expect(cfgBox!.y).toBeGreaterThan(cpBox!.y + 50)

    // Context Summary to the right of Configuration (same row)
    expect(csBox!.x).toBeGreaterThan(cfgBox!.x)
  })
})

test.describe('Control Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('voice channel selector exists', async ({ page }) => {
    await expect(page.locator('#channel-select')).toBeVisible()
    await expect(page.locator('#join-btn')).toBeVisible()
    await expect(page.locator('#leave-btn')).toBeVisible()
  })

  test('AI mode buttons exist with correct labels', async ({ page }) => {
    await expect(page.locator('#mode-passive')).toBeVisible()
    await expect(page.locator('#mode-speech-to-speech')).toBeVisible()
    await expect(page.locator('#mode-ask-chatgpt')).toBeVisible()

    await expect(page.locator('#mode-passive')).toContainText('Passive')
    await expect(page.locator('#mode-speech-to-speech')).toContainText('Speech')
    await expect(page.locator('#mode-ask-chatgpt')).toContainText('ChatGPT')
  })

  test('current mode indicator shows default', async ({ page }) => {
    await expect(page.locator('#current-mode')).toBeVisible()
    await expect(page.locator('#mode-description')).toBeVisible()
  })

  test('force response button exists', async ({ page }) => {
    await expect(page.locator('#force-response')).toBeVisible()
    await expect(page.locator('#force-response')).toContainText('Force AI Response')
  })

  test('documents section exists with upload button', async ({ page }) => {
    await expect(page.locator('#upload-btn')).toBeVisible()
    await expect(page.locator('#documents-list')).toBeVisible()
    await expect(page.locator('#docs-to-context')).toBeVisible()
  })
})

test.describe('Ask ChatGPT Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('input textarea and send button exist', async ({ page }) => {
    await expect(page.locator('#chatgpt-input')).toBeVisible()
    await expect(page.locator('#chatgpt-send')).toBeVisible()
    await expect(page.locator('#chatgpt-send')).toContainText('Ask ChatGPT')
  })

  test('response area exists', async ({ page }) => {
    await expect(page.locator('#chatgpt-response')).toBeVisible()
  })

  test('clear and to-context buttons exist', async ({ page }) => {
    await expect(page.locator('#clear-chatgpt')).toBeVisible()
    await expect(page.locator('#chatgpt-to-context')).toBeVisible()
  })

  test('can type in the input textarea', async ({ page }) => {
    await page.locator('#chatgpt-input').fill('Hello, this is a test question')
    await expect(page.locator('#chatgpt-input')).toHaveValue('Hello, this is a test question')
  })
})

test.describe('Configuration Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('provider dropdowns exist', async ({ page }) => {
    await expect(page.locator('#reasoning-model-select')).toBeVisible()
    await expect(page.locator('#tts-voice-select')).toBeVisible()
    await expect(page.locator('#tts-provider-select')).toBeVisible()
    await expect(page.locator('#stt-provider-select')).toBeVisible()
  })

  test('session spend start/stop buttons exist', async ({ page }) => {
    await expect(page.locator('#session-start')).toBeVisible()
    await expect(page.locator('#session-stop')).toBeVisible()
    await expect(page.locator('#session-status')).toBeVisible()
  })

  test('session summary is hidden initially', async ({ page }) => {
    await expect(page.locator('#session-summary')).toBeHidden()
  })

  test('session status shows ready message', async ({ page }) => {
    await expect(page.locator('#session-status')).toContainText('Ready')
  })
})

test.describe('Right Side Panels', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
  })

  test('live conversation panel has transcript container', async ({ page }) => {
    await expect(page.locator('#transcript-container')).toBeVisible()
    await expect(page.locator('#export-transcript')).toBeVisible()
    await expect(page.locator('#refresh-transcript')).toBeVisible()
  })

  test('AI insights panel has observer controls', async ({ page }) => {
    await expect(page.locator('#observer-insights')).toBeVisible()
    await expect(page.locator('#observer-toggle')).toBeVisible()
    await expect(page.locator('#observer-frequency')).toBeVisible()
    await expect(page.locator('#observer-status')).toBeVisible()
  })

  test('context summary panel has generate and export buttons', async ({ page }) => {
    await expect(page.locator('#generate-summary')).toBeVisible()
    await expect(page.locator('#export-context')).toBeVisible()
    await expect(page.locator('#context-summary')).toBeVisible()
  })
})
