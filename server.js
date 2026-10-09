import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const root = path.dirname(fileURLToPath(import.meta.url));
const profileDir = path.join(root, '.linkedin-chromium-profile');
let context;

async function openLinkedIn() {
  if (!context) {
    context = await chromium.launchPersistentContext(profileDir, {
      headless: false,
      viewport: { width: 1440, height: 950 },
      args: ['--disable-blink-features=AutomationControlled']
    });
    context.on('close', () => { context = undefined; });
  }
  const page = context.pages()[0] || await context.newPage();
  await page.goto('https://www.linkedin.com/', { waitUntil: 'domcontentloaded' });
  return page.url().includes('/login')
    ? 'Chromium opened — log in manually once, then close it to persist the session.'
    : 'Persisted LinkedIn session opened.';
}

const HOST = '127.0.0.1';
const PORT = Number(process.env.PORT) || 8000;
const PUBLIC_FILES = new Set(['/index.html', '/app.js', '/styles.css']);
const mime = { '.html':'text/html; charset=utf-8', '.css':'text/css', '.js':'text/javascript', '.md':'text/plain' };
const server = http.createServer(async (req, res) => {
  try {
    if (req.method === 'POST' && req.url === '/api/linkedin/connect') {
      const message = await openLinkedIn();
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(JSON.stringify({ message }));
    }
    const requested = req.url === '/' ? '/index.html' : req.url.split('?')[0];
    if (!PUBLIC_FILES.has(requested)) return res.writeHead(404).end('Not found');
    const file = path.join(root, requested);
    const body = await fs.readFile(file);
    res.writeHead(200, { 'Content-Type': mime[path.extname(file)] || 'application/octet-stream' });
    res.end(body);
  } catch (error) {
    console.error(error);
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Unable to open Chromium. Run npm install and npm run install-browser.' }));
  }
});

server.listen(PORT, HOST, () => console.log(`HireBuddy running at http://${HOST}:${PORT}`));
process.on('SIGINT', async () => { if (context) await context.close(); server.close(); });
