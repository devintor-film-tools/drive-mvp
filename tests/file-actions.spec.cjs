const { test, expect } = require('../frontend/node_modules/@playwright/test');
const { randomUUID } = require('node:crypto');
const fs = require('node:fs/promises');

test.beforeEach(async ({ page }) => {
  test.skip(!process.env.DRIVE_TEST_USER_B, 'Requires disposable test accounts.');
  await page.goto('/');
  await page.getByLabel('Username', { exact: true }).fill(process.env.DRIVE_TEST_USER_B);
  await page.getByLabel('Password', { exact: true }).fill(process.env.DRIVE_TEST_PASSWORD_B);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'My Drive', exact: true })).toBeVisible();
});
async function upload(page) {
  const name = `actions-${randomUUID()}.txt`;
  await page.locator('input[type=file]').setInputFiles({ name, mimeType: 'text/plain', buffer: Buffer.from('file actions fixture') });
  await expect(page.getByRole('heading', { name: '1 upload complete', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Dismiss', exact: true }).click();
  return name;
}
async function action(page, name, label) {
  await page.getByRole('button', { name: `Actions for ${name}`, exact: true }).click();
  await page.getByRole('menuitem', { name: label, exact: true }).click();
}
test('download exact bytes, keyboard rename, trash, refresh and restore', async ({ page }, testInfo) => {
  const name = await upload(page);
  const trigger = page.getByRole('button', { name: `Actions for ${name}`, exact: true });
  await trigger.focus(); await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('menuitem', { name: 'Download', exact: true })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(trigger).toBeFocused();
  const downloading = page.waitForEvent('download');
  await action(page, name, 'Download');
  const download = await downloading;
  expect(download.suggestedFilename()).toBe(name);
  expect((await fs.readFile(await download.path())).toString()).toBe('file actions fixture');
  await expect(page.getByText('Download sent to your browser. Check your downloads.')).toBeVisible();
  await action(page, name, 'Rename…');
  await expect(page.getByLabel('File name', { exact: true })).toBeFocused();
  await page.keyboard.press('Escape'); await expect(trigger).toBeFocused();
  await action(page, name, 'Rename…');
  const renamed = `renamed-${randomUUID()}.txt`;
  await page.getByLabel('File name', { exact: true }).fill(renamed);
  await page.screenshot({ path: testInfo.outputPath('rename-desktop.png') });
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('row').filter({ hasText: renamed })).toBeVisible();
  await action(page, renamed, 'Move to trash');
  await expect(page.getByRole('row').filter({ hasText: renamed })).toHaveCount(0);
  await page.getByRole('button', { name: 'Trash', exact: true }).click();
  await expect(page.getByRole('row').filter({ hasText: renamed })).toBeVisible();
  await page.reload();
  // Navigation starts in My Drive on reload; the persisted trash state remains.
  await page.getByRole('button', { name: 'Trash', exact: true }).click();
  await expect(page.getByRole('row').filter({ hasText: renamed })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('trash-desktop.png') });
  await action(page, renamed, 'Restore');
  await expect(page.getByRole('row').filter({ hasText: renamed })).toHaveCount(0);
  await page.getByRole('button', { name: 'My Drive', exact: true }).click();
  await expect(page.getByRole('row').filter({ hasText: renamed })).toBeVisible();
});
test('narrow layout, invalid rename and failed download remain recoverable', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const name = await upload(page);
  await action(page, name, 'Rename…');
  await page.getByLabel('File name', { exact: true }).fill('../invalid');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toBeVisible();
  await expect(page.getByLabel('File name', { exact: true })).toHaveValue('../invalid');
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.route('**/api/files/*/content', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({error:{code:'file_unavailable'}}) }));
  await action(page, name, 'Download');
  await expect(page.getByText('The file couldn’t be downloaded. Please try again.')).toBeVisible();
  await expect(page.getByRole('row').filter({ hasText: name })).toBeVisible();
  await page.getByRole('button', { name: 'Trash', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Trash', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'My Drive', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.getByRole('heading', { name: 'Loading your files…' })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('trash-narrow.png') });
});

test('stale tab cannot overwrite a rename; lost trash response is recoverable', async ({ page, context }) => {
  const name = await upload(page);
  const stale = await context.newPage();
  await stale.goto('/');
  await expect(stale.getByRole('button', { name: `Actions for ${name}`, exact: true })).toBeVisible();
  const renamed = `current-${randomUUID()}.txt`;
  await action(page, name, 'Rename…');
  await page.getByLabel('File name', { exact: true }).fill(renamed);
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(page.getByRole('button', { name: `Actions for ${renamed}`, exact: true })).toBeVisible();
  await action(stale, name, 'Rename…');
  await stale.getByLabel('File name', { exact: true }).fill('stale.txt');
  await stale.getByRole('button', { name: 'Save', exact: true }).click();
  await expect(stale.getByRole('dialog').getByRole('alert')).toContainText('changed in another tab');
  await stale.getByRole('button', { name: 'Cancel', exact: true }).click();
  await stale.getByRole('button', { name: 'Refresh list', exact: true }).click();
  await expect(stale.getByRole('button', { name: `Actions for ${renamed}`, exact: true })).toBeVisible();
  await stale.close();
  let patches = 0;
  await page.route('**/api/files/*', async route => {
    if (route.request().method() !== 'PATCH') return route.continue();
    patches++;
    const response = await route.fetch(); expect(response.status()).toBe(200);
    await route.abort('connectionreset');
  });
  await action(page, renamed, 'Move to trash');
  await expect(page.getByRole('alert')).toContainText('couldn’t confirm');
  await page.getByRole('button', { name: 'Refresh list', exact: true }).click();
  await expect(page.getByRole('row').filter({ hasText: renamed })).toHaveCount(0);
  await page.getByRole('button', { name: 'Trash', exact: true }).click();
  await expect(page.getByRole('row').filter({ hasText: renamed })).toHaveCount(1);
  expect(patches).toBe(1);
  // Retain this trashed fixture for the harness's restart/backup/restore checks.
});
