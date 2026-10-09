import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
let child;
let port;

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
    srv.on('error', reject);
  });
}

before(async () => {
  port = await freePort();
  child = spawn(process.execPath, ['server.js'], { cwd: root, env: { ...process.env, PORT: String(port) } });
  await new Promise((resolve, reject) => {
    child.stdout.on('data', (chunk) => String(chunk).includes('running at') && resolve());
    child.on('error', reject);
    child.on('exit', (code) => reject(new Error(`server exited early with code ${code}`)));
  });
});

after(() => child?.kill('SIGINT'));

const get = (p) => fetch(`http://127.0.0.1:${port}${p}`);

test('serves the three front-end files', async () => {
  for (const [url, type] of [['/', 'text/html'], ['/index.html', 'text/html'], ['/app.js', 'text/javascript'], ['/styles.css', 'text/css']]) {
    const res = await get(url);
    assert.equal(res.status, 200, url);
    assert.ok(res.headers.get('content-type').startsWith(type), url);
  }
});

test('ignores a query string on allowed files', async () => {
  assert.equal((await get('/app.js?v=2')).status, 200);
});

test('does not serve anything else from the project root', async () => {
  for (const url of ['/package.json', '/package-lock.json', '/server.js', '/README.md', '/PrabhatSaxena.pdf', '/.gitignore', '/ingestion/ingest.py']) {
    assert.equal((await get(url)).status, 404, url);
  }
});

test('rejects path traversal attempts', async () => {
  for (const url of ['/../server.js', '/%2e%2e/server.js', '/..%2fserver.js']) {
    assert.equal((await get(url)).status, 404, url);
  }
});

test('listens on loopback only', async (t) => {
  const lan = Object.values(os.networkInterfaces()).flat().find((i) => i.family === 'IPv4' && !i.internal);
  if (!lan) return t.skip('no non-loopback IPv4 interface on this machine');
  await assert.rejects(fetch(`http://${lan.address}:${port}/`), /fetch failed/);
});
