// Lottie -> PNG frames using puppeteer + lottie-web (CDN)
// Renders each frame of the animation to a PNG file.
// Usage: node scripts/lottie_to_frames.js <input.json> <output_size> <frame_step>
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const INPUT_JSON = process.argv[2] || path.resolve(__dirname, '..', 'developer skills.json');
const OUTPUT_SIZE = parseInt(process.argv[3] || '576', 10);
const FRAME_STEP = parseInt(process.argv[4] || '2', 10);

const PROJECT_ROOT = path.resolve(__dirname, '..');
const FRAMES_DIR = path.join(PROJECT_ROOT, '.preview', 'frames');

async function main() {
  const lottieData = fs.readFileSync(INPUT_JSON, 'utf-8');
  const parsed = JSON.parse(lottieData);
  const aspectRatio = parsed.w / parsed.h;
  const renderW = OUTPUT_SIZE;
  const renderH = Math.round(OUTPUT_SIZE / aspectRatio);

  console.log(`Input: ${INPUT_JSON}`);
  console.log(`Source: ${parsed.w}x${parsed.h}, aspect: ${aspectRatio.toFixed(2)}`);
  console.log(`Render: ${renderW}x${renderH}, frame step: ${FRAME_STEP}`);

  if (!fs.existsSync(FRAMES_DIR)) fs.mkdirSync(FRAMES_DIR, { recursive: true });

  const html = `<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/bodymovin/5.12.2/lottie.min.js"></script>
<style>
  body { margin:0; background:transparent; display:flex; align-items:center; justify-content:center; height:100vh; }
  #anim { width:${renderW}px; height:${renderH}px; }
</style>
</head>
<body>
<div id="anim"></div>
<script>
  const data = ${lottieData};
  let anim = null;
  window._ready = false;
  window._renderFrame = function(frame) { anim.goToAndStop(frame, true); };
  window._getFrameCount = function() { return anim.totalFrames; };
  window._getCanvas = function() {
    const c = document.querySelector('#anim canvas');
    return c ? c.toDataURL('image/png') : null;
  };
  function init() {
    if (typeof lottie === 'undefined') { setTimeout(init, 50); return; }
    anim = lottie.loadAnimation({
      container: document.getElementById('anim'),
      renderer: 'canvas',
      loop: false,
      autoplay: false,
      animationData: data,
      rendererSettings: { scale: ${renderW}/${parsed.w} }
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
  await page.setViewport({ width: renderW + 20, height: renderH + 20, deviceScaleFactor: 1 });

  console.log('Loading page with Lottie animation...');
  await page.setContent(html, { waitUntil: 'networkidle0' });

  console.log('Waiting for Lottie to initialize...');
  await page.waitForFunction('window._ready === true', { timeout: 30000 });

  const totalFrames = await page.evaluate(() => window._getFrameCount());
  console.log(`Total frames: ${totalFrames}, capturing every ${FRAME_STEP}nd frame...`);

  let captured = 0;
  for (let f = 0; f < totalFrames; f += FRAME_STEP) {
    await page.evaluate((frame) => window._renderFrame(frame), f);
    await new Promise(r => setTimeout(r, 30));
    const dataUrl = await page.evaluate(() => window._getCanvas());
    if (dataUrl) {
      const base64 = dataUrl.replace(/^data:image\/png;base64,/, '');
      const framePath = path.join(FRAMES_DIR, `frame_${String(captured).padStart(4, '0')}.png`);
      fs.writeFileSync(framePath, Buffer.from(base64, 'base64'));
      captured++;
      if (captured % 30 === 0) console.log(`  captured ${captured} frames...`);
    }
  }

  console.log(`Done. Captured ${captured} frames to ${FRAMES_DIR}`);
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
