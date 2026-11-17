const { defineConfig } = require('../frontend/node_modules/@playwright/test');

module.exports = defineConfig({
  testDir: __dirname,
  testMatch: '**/*.spec.cjs',
  workers: 1,
  fullyParallel: false,
  timeout: 45_000,
  retries: 0,
  reporter: 'list',
  outputDir: process.env.DRIVE_TEST_ARTIFACT_DIR || '/tmp/drive-mvp-playwright-results',
  use: {
    baseURL: process.env.DRIVE_TEST_BASE_URL || 'http://127.0.0.1:8000',
    viewport: { width: 1280, height: 800 },
    screenshot: 'only-on-failure',
    trace: 'off',
  },
});
