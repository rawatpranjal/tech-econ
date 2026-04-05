#!/usr/bin/env node
/**
 * screenshot-homepage.js
 * Takes full-page and above-the-fold screenshots of the Hugo dev server.
 *
 * Usage:
 *   node scripts/screenshot-homepage.js
 *   node scripts/screenshot-homepage.js --port 1313 --out /tmp/homepage.png
 *
 * Output:
 *   /tmp/homepage.png       — full page
 *   /tmp/homepage-fold.png  — above the fold (1440×900 viewport)
 */

const { chromium } = require('playwright');

async function main() {
  const args = process.argv.slice(2);

  const portIdx = args.indexOf('--port');
  const port = portIdx !== -1 ? args[portIdx + 1] : '1313';

  const outIdx = args.indexOf('--out');
  const out = outIdx !== -1 ? args[outIdx + 1] : '/tmp/homepage.png';
  const foldOut = out.replace(/\.png$/, '-fold.png');

  const url = `http://localhost:${port}`;
  console.log(`Screenshotting ${url} ...`);

  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
  } catch (e) {
    console.error(`Could not reach ${url} — is hugo server running?`);
    console.error(`Start it with: hugo server --port ${port} &`);
    await browser.close();
    process.exit(1);
  }

  // Full page
  await page.screenshot({ path: out, fullPage: true });
  console.log(`Full page  → ${out}`);

  // Above the fold only
  await page.screenshot({ path: foldOut, fullPage: false });
  console.log(`Above fold → ${foldOut}`);

  await browser.close();
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
