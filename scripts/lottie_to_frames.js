// Lottie -> PNG frames using puppeteer + lottie-web (CDN)
// Renders each frame of the animation to a PNG file.
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const PROJECT_ROOT = path.resolve(__dirname, '..');
const LOTTIE_JSON = path.join(PROJECT_ROOT, 'developer skills.json');
const FRAMES_DIR = path.join(PROJECT_ROOT, '.preview', 'frames');
const OUTPUT_SIZE = 480; // render at 480x480 to keep GIF small
const FRAME_STEP = 2;    // capture every 2nd frame (125 frames at ~12.5fps)

async function main() {
  // Read the Lottie JSON
  const lottieData = fs.readFileSync(LOTTIE_JSON, 'utf-8');

  // Ensure frames dir exists
  if (!fs.existsSync(FRAMES_DIR)) fs.mkdirSync(FRAMES_DIR, { recursive: true });

  // Build HTML with lottie-web from CDN and inlined JSON
  const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/bodymovin/5.12.2/lottie.min.js"></script>
<style>
  body { margin:0; background:#0d1117; display:flex; align-items:center; justify-content:center; height:100vh; }
  #anim { width:${OUTPUT_SIZE}px; height:${OUTPUT_SIZE}px; }
</style>
</head>
<body>
<div id="anim"></div>
<script>
  const data = ${lottieData};
  let anim = null;
  window._ready = false;
  window._renderFrame = function(frame) {
    anim.goToAndStop(frame, true);
  };
  window._getFrameCount = function() { return anim.totalFrames; };
  window._getCanvas = function() {
    const c = document.querySelector('#anim canvas');
    return c ? c.toDataURL('image/png') : null;
  };
  // Wait for lottie library to load
  function init() {
    if (typeof lottie === 'undefined') { setTimeout(init, 50); return; }
    anim = lottie.loadAnimation({
      container: document.getElementById('anim'),
      renderer: 'canvas',
      loop: false,
      autoplay: false,
      animationData: data,
      rendererSettings: { scale: ${OUTPUT_SIZE}/1000 }
    });
    anim.addEventListener('DOMLoaded', () => { window._ready = true; });
  }
  init();
</script>
</body></html>`;

  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.setViewport({ width: OUTPUT_SIZE + 20, height: OUTPUT_SIZE + 20, deviceScaleFactor: 1 });

  console.log('Loading page with Lottie animation...');
  await page.setContent(html, { waitUntil: 'networkidle0' });

  // Wait for lottie to be ready
  console.log('Waiting for Lottie to initialize...');
  await page.waitForFunction('window._ready === true', { timeout: 30000 });

  const totalFrames = await page.evaluate(() => window._getFrameCount());
  console.log(`Total frames: ${totalFrames}, capturing every ${FRAME_STEP}nd frame...`);

  let captured = 0;
  for (let f = 0; f < totalFrames; f += FRAME_STEP) {
    await page.evaluate((frame) => window._renderFrame(frame), f);
    // Small delay to let canvas render settle
    await new Promise(r => setTimeout(r, 30));
    const dataUrl = await page.evaluate(() => window._getCanvas());
    if (dataUrl) {
      const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
      const framePath = path.join(FRAMES_DIR, `frame_${String(captured).padStart(4, '0')}.png`);
      fs.writeFileSync(framePath, Buffer.from(base64, 'base64'));
      captured++;
      if (captured % 20 === 0) console.log(`  captured ${captured} frames...`);
    }
  }

  console.log(`Done. Captured ${captured} frames to ${FRAMES_DIR}`);
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
