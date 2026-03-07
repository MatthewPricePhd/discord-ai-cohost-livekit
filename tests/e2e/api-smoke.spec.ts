import { test, expect } from '@playwright/test'

test.describe('API Smoke Tests', () => {
  test('GET /api/status returns valid response', async ({ request }) => {
    const res = await request.get('/api/status')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('running')
    expect(body).toHaveProperty('mode')
    expect(body).toHaveProperty('web_server_running')
    expect(body.web_server_running).toBe(true)
  })

  test('GET /api/discord/guilds returns array', async ({ request }) => {
    const res = await request.get('/api/discord/guilds')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('guilds')
    expect(Array.isArray(body.guilds)).toBe(true)
  })

  test('GET /api/documents returns list', async ({ request }) => {
    const res = await request.get('/api/documents')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('documents')
    expect(Array.isArray(body.documents)).toBe(true)
  })

  test('GET /api/conversation/transcript returns data', async ({ request }) => {
    const res = await request.get('/api/conversation/transcript')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('transcript')
  })

  test('GET /api/session/status returns session info', async ({ request }) => {
    const res = await request.get('/api/session/status')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('running')
    expect(typeof body.running).toBe('boolean')
  })

  test('GET /api/providers returns provider config', async ({ request }) => {
    const res = await request.get('/api/providers')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('tts_provider')
    expect(body).toHaveProperty('stt_provider')
  })

  test('GET /api/voices returns voice list', async ({ request }) => {
    const res = await request.get('/api/voices')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('voices')
  })

  test('GET /api/observer/insights returns observer data', async ({ request }) => {
    const res = await request.get('/api/observer/insights')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('enabled')
    expect(body).toHaveProperty('insights')
  })

  test('GET /api/logs returns log entries', async ({ request }) => {
    const res = await request.get('/api/logs')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('logs')
    expect(Array.isArray(body.logs)).toBe(true)
  })

  test('POST /api/session/start starts a session', async ({ request }) => {
    const res = await request.post('/api/session/start')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('success')
    expect(body.success).toBe(true)
    expect(body).toHaveProperty('start_time')

    // Clean up - stop the session
    await request.post('/api/session/stop', {
      data: { start_time: body.start_time }
    })
  })

  test('POST /api/session/stop returns cost data', async ({ request }) => {
    // Start a session first
    const startRes = await request.post('/api/session/start')
    const startBody = await startRes.json()

    const res = await request.post('/api/session/stop', {
      data: { start_time: startBody.start_time }
    })
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('success')
    expect(body).toHaveProperty('total_usd')
    expect(typeof body.total_usd).toBe('number')
  })

  test('POST /api/mode/passive sets passive mode', async ({ request }) => {
    const res = await request.post('/api/mode/passive')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body).toHaveProperty('success')
  })
})
