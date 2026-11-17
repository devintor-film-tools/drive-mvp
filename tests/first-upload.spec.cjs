const { test, expect } = require('../frontend/node_modules/@playwright/test');
const { randomUUID } = require('node:crypto');

const username = process.env.DRIVE_TEST_USER_B;
const password = process.env.DRIVE_TEST_PASSWORD_B;

test.beforeEach(async ({ page, baseURL }) => {
  test.skip(!username || !password, 'Supply disposable fixture credentials in DRIVE_TEST_USER_B/PASSWORD_B.');
  expect(['127.0.0.1', 'localhost', '[::1]']).toContain(new URL(baseURL).hostname);
  await page.goto('/');
  await page.getByLabel('Username', { exact: true }).fill(username);
  await page.getByLabel('Password', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'My Drive', exact: true })).toBeVisible();
});

async function selectFile(page, name, content) {
  await page.getByRole('button', { name: 'New', exact: true }).click();
  const chooserPromise = page.waitForEvent('filechooser');
  await page.getByRole('menuitem', { name: 'File upload', exact: true }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles({ name, mimeType: 'application/octet-stream', buffer: content });
}

test('keyboard menu, real upload, exact retrieval, dismiss and refresh', async ({ page, context }, testInfo) => {
  const newButton = page.getByRole('button', { name: 'New', exact: true });
  await newButton.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('menuitem', { name: 'File upload', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(newButton).toBeFocused();
  await expect(newButton).toHaveAttribute('aria-expanded', 'false');

  const name = `browser-${randomUUID()}.bin`;
  const content = Buffer.from('A private browser upload\n\x00\xff', 'latin1');
  await selectFile(page, name, content);
  await expect(page.getByRole('heading', { name: '1 upload complete', exact: true })).toBeVisible();
  const row = page.getByRole('row').filter({ hasText: name });
  await expect(row).toHaveCount(1);
  const response = await context.request.get('/api/files');
  expect(response.status()).toBe(200);
  const saved = (await response.json()).items.find(item => item.name === name);
  expect(saved).toBeTruthy();
  const download = await context.request.get(`/api/files/${saved.id}/content`);
  expect(download.status()).toBe(200);
  expect((await download.body()).equals(content)).toBe(true);

  await page.getByRole('button', { name: 'Dismiss', exact: true }).click();
  await expect(row).toHaveCount(1);
  await expect(page.getByRole('heading', { name: 'My Drive', exact: true })).toBeFocused();
  await page.reload();
  await expect(page.getByRole('row').filter({ hasText: name })).toHaveCount(1);
  await page.screenshot({ path: testInfo.outputPath('desktop.png'), fullPage: true });
});

test('lost successful PUT response reconciles without a duplicate upload', async ({ page, context }) => {
  const name = `uncertain-${randomUUID()}.bin`;
  let putCount = 0;
  await page.route('**/api/uploads/*/content', async route => {
    if (route.request().method() !== 'PUT') return route.continue();
    putCount += 1;
    const saved = await route.fetch();
    expect(saved.status()).toBe(200);
    await route.abort('connectionreset');
  });
  await selectFile(page, name, Buffer.from('Saved before the browser receives confirmation.'));
  await expect(page.getByRole('heading', { name: '1 upload complete', exact: true })).toBeVisible();
  expect(putCount).toBe(1);
  const response = await context.request.get('/api/files');
  expect((await response.json()).items.filter(item => item.name === name)).toHaveLength(1);
  await expect(page.getByRole('row').filter({ hasText: name })).toHaveCount(1);
});

test('a failed list is distinct from an empty drive and recovers', async ({ page }) => {
  const name = `list-recovery-${randomUUID()}.bin`;
  await selectFile(page, name, Buffer.from('A file that must survive a failed list request.'));
  await expect(page.getByRole('heading', { name: '1 upload complete', exact: true })).toBeVisible();
  await page.route('**/api/files*', route => route.abort('connectionfailed'));
  await page.reload();
  await expect(page.getByText(/couldn.t load|couldn.t be loaded|could not load|files couldn.t load/i).first()).toBeVisible();
  await expect(page.getByText('A place for your files', { exact: true })).toHaveCount(0);
  await page.unroute('**/api/files*');
  await page.getByRole('button', { name: /try again|retry/i }).click();
  await expect(page.getByRole('table')).toBeVisible();
  await expect(page.getByRole('row').filter({ hasText: name })).toHaveCount(1);
});

test('narrow layout retains the upload entry point without horizontal overflow', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: 'New', exact: true })).toBeVisible();
  const width = await page.evaluate(() => ({ content: document.documentElement.scrollWidth, viewport: innerWidth }));
  expect(width.content).toBeLessThanOrEqual(width.viewport);
  await page.screenshot({ path: testInfo.outputPath('mobile.png'), fullPage: true });
});
