// Extract contribution calendar data from GitHub profile using puppeteer
// Outputs JSON to stdout: { "contributions": [{ "date": "YYYY-MM-DD", "count": N }, ...] }
const puppeteer = require('puppeteer');

async function main() {
  const username = process.argv[2] || 'ChitkulLakshya';
  const url = `https://github.com/${username}`;

  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 800 });

  console.error(`Loading ${url}...`);
  await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });

  // Wait for the contribution graph to render
  console.error('Waiting for contribution graph...');
  try {
    await page.waitForSelector('[data-date]', { timeout: 15000 });
  } catch (e) {
    console.error('Contribution graph not found, trying alternative selectors...');
    // Try newer GitHub structure
    try {
      await page.waitForSelector('.ContributionCalendar-day', { timeout: 10000 });
    } catch (e2) {
      console.error('Could not find contribution data');
      console.log(JSON.stringify({ contributions: [] }));
      await browser.close();
      return;
    }
  }

  // Extract contribution data from the DOM
  const data = await page.evaluate(() => {
    const contributions = [];

    // Try data-date + data-count attributes (older structure)
    const rects = document.querySelectorAll('[data-date]');
    rects.forEach(el => {
      const date = el.getAttribute('data-date');
      const count = parseInt(el.getAttribute('data-count') || '0', 10);
      if (date) {
        contributions.push({ date, count });
      }
    });

    // Try newer structure: .ContributionCalendar-day with data-date
    if (contributions.length === 0) {
      const days = document.querySelectorAll('.ContributionCalendar-day, [class*="ContributionCalendar"]');
      days.forEach(el => {
        const date = el.getAttribute('data-date');
        if (!date) return;
        const countText = el.getAttribute('data-count') || el.textContent || '0';
        const count = parseInt(countText.match(/\d+/)?.[0] || '0', 10);
        contributions.push({ date, count });
      });
    }

    // Try scraping from tooltips or aria-labels
    if (contributions.length === 0) {
      const cells = document.querySelectorAll('td[aria-label], rect[aria-label]');
      cells.forEach(el => {
        const label = el.getAttribute('aria-label') || '';
        const match = label.match(/(\d+).*contributions?.*on\s+(\w+\s+\d+,?\s+\d+)/i);
        if (match) {
          const count = parseInt(match[1], 10);
          const date = new Date(match[2]).toISOString().split('T')[0];
          contributions.push({ date, count });
        }
      });
    }

    return { contributions };
  });

  console.log(JSON.stringify(data));
  console.error(`Extracted ${data.contributions.length} days of contribution data`);
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
