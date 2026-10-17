'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
const { once } = require('node:events');
const { createDevServer, validateBackend, parseArguments } = require('../dev-server.cjs');

const SYSTEM = { name: 'Synthetic ArchGuard', version: '0.0.0-test', status: 'foundation', iam_schema_version: '1.0', finding_schema_version: '1.0' };

async function listen(server) {
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  return server.address().port;
}

async function close(server) {
  server.closeAllConnections();
  await new Promise(resolve => server.close(resolve));
}

async function fixture(t, options = {}) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'archguard-bridge-test-'));
  await fs.writeFile(path.join(root, 'index.html'), '<!doctype html><title>Synthetic</title>');
  await fs.writeFile(path.join(root, 'app.js'), '/* synthetic */');
  await fs.writeFile(path.join(root, '.private.txt'), 'not-served');
  const server = createDevServer({ root, ...options });
  const port = await listen(server);
  t.after(async () => { await close(server); await fs.rm(root, { recursive: true, force: true }); });
  return { root, server, port };
}

async function upstream(t, handler) {
  const requests = [];
  const server = http.createServer((request, response) => {
    requests.push(request.url);
    handler(request, response);
  });
  const port = await listen(server);
  t.after(() => close(server));
  return { server, requests, url: `http://127.0.0.1:${port}` };
}

function json(response, data, status = 200) {
  response.writeHead(status, { 'Content-Type': 'application/json' });
  response.end(JSON.stringify(data));
}

function request(port, target = '/', options = {}) {
  return new Promise((resolve, reject) => {
    const outgoing = http.request({ hostname: '127.0.0.1', port, path: target, method: options.method || 'GET', headers: options.headers || {}, agent: false }, response => {
      const chunks = [];
      response.on('data', chunk => chunks.push(chunk));
      response.on('end', () => resolve({ status: response.statusCode, headers: response.headers, text: Buffer.concat(chunks).toString('utf8') }));
      response.on('error', reject);
    });
    outgoing.on('error', reject);
    outgoing.end(options.body);
  });
}

test('configuration accepts literal loopback HTTP only and validates CLI options', () => {
  for (const value of ['http://127.0.0.1:8780', 'http://127.0.0.2:8080/', 'http://[::1]:8780']) {
    assert.ok(validateBackend(value) instanceof URL);
  }
  for (const value of ['https://127.0.0.1:8780', 'http://localhost:8780', 'http://0.0.0.0:8780', 'http://192.168.1.1', 'http://10.0.0.1', 'http://example.com', 'http://127.1', 'http://2130706433', 'http://0x7f000001', 'http://127.0.0.999', 'http://user:pass@127.0.0.1', 'http://127.0.0.1/path', 'http://127.0.0.1/?x=1', 'http://127.0.0.1/#x', 'http://127.0.0.1:0', 'http://127.0.0.1:65536', 'http://127.0.0.1%2f.example.com']) {
    assert.throws(() => validateBackend(value), /BACKEND_URL_INVALID/, value);
  }
  assert.equal(validateBackend(null), null);
  assert.deepEqual(parseArguments([]), { port: 8779, backend: null });
  assert.deepEqual(parseArguments(['--port', '8781', '--backend', 'http://127.0.0.1:8780']), { port: 8781, backend: 'http://127.0.0.1:8780' });
  for (const args of [['--root', '/tmp'], ['--port'], ['--port', '0'], ['--port', '65536'], ['--port', 'x'], ['--port', '8779', '--port', '8780']]) {
    assert.throws(() => parseArguments(args));
  }
});

test('static GET and HEAD stay inside artifact root, with same-origin headers', async t => {
  const { port } = await fixture(t);
  const get = await request(port);
  assert.equal(get.status, 200);
  assert.match(get.text, /Synthetic/);
  assert.match(get.headers['content-type'], /^text\/html/);
  assert.equal(get.headers['x-content-type-options'], 'nosniff');
  assert.equal(get.headers['cross-origin-resource-policy'], 'same-origin');
  assert.equal(get.headers['cache-control'], 'no-store');
  assert.equal(get.headers['access-control-allow-origin'], undefined);
  const head = await request(port, '/', { method: 'HEAD' });
  assert.equal(head.status, 200);
  assert.equal(head.text, '');
  assert.equal(head.headers['content-length'], get.headers['content-length']);
  assert.equal((await request(port, '/app.js?revision=1')).status, 200);
  assert.equal((await request(port, '/missing.html')).status, 404);
  assert.equal((await request(port, '/dev-server.cjs')).status, 404);
  assert.equal((await request(port, '/', { headers: { Origin: `http://127.0.0.1:${port}` } })).status, 200);
});

test('rejects foreign Host, Origin, methods and request bodies before upstream access', async t => {
  const backend = await upstream(t, (_request, response) => json(response, {}));
  const { port } = await fixture(t, { backend: backend.url });
  for (const headers of [{ Host: 'evil.example' }, { Host: `localhost:${port}` }, { Origin: 'https://evil.example' }, { Origin: 'null' }, { Origin: `http://127.0.0.1:${port + 1}` }]) {
    assert.equal((await request(port, '/__bridge/system', { headers })).status, 403);
  }
  for (const method of ['POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']) {
    const result = await request(port, '/__bridge/system', { method });
    assert.equal(result.status, 405);
    assert.equal(result.headers.allow, 'GET, HEAD');
  }
  assert.equal((await request(port, '/__bridge/system', { method: 'HEAD' })).status, 405);
  assert.equal((await request(port, '/', { headers: { 'Content-Length': '1' }, body: 'x' })).status, 400);
  assert.equal(backend.requests.length, 0);
});

test('rejects traversal, encoded separators, hidden paths, special files and symlinks', async t => {
  const { root, port } = await fixture(t);
  const outside = await fs.mkdtemp(path.join(os.tmpdir(), 'archguard-outside-test-'));
  t.after(() => fs.rm(outside, { recursive: true, force: true }));
  await fs.writeFile(path.join(outside, 'outside.txt'), 'must not be served');
  await fs.mkdir(path.join(root, 'subdir'));
  await fs.mkdir(path.join(root, '.hidden'));
  await fs.writeFile(path.join(root, '.hidden', 'index.html'), 'hidden');
  await fs.symlink(path.join(outside, 'outside.txt'), path.join(root, 'link.txt'));
  await fs.symlink(outside, path.join(root, 'linked-dir'));
  await fs.symlink(path.join(root, 'app.js'), path.join(root, 'internal-link.js'));
  for (const target of ['/../outside.txt', '/%2e%2e/outside.txt', '/subdir/../app.js', '/%2eprivate.txt', '/.private.txt', '/.hidden/index.html', '/subdir%2f..%2fapp.js', '/subdir%5c..%5capp.js', '/%252e%252e/outside.txt', '/%00.html', '//app.js', '/app.js#fragment', '/bad%xx.html', '/link.txt', '/linked-dir/outside.txt', '/internal-link.js']) {
    const result = await request(port, target);
    assert.equal(result.status, 403, target);
    assert.doesNotMatch(result.text, /must not be served|not-served|archguard-outside-test/);
  }
  assert.equal((await request(port, '/subdir')).status, 404);
});

test('missing backend is explicitly unavailable and bridge route is exact', async t => {
  const { port } = await fixture(t);
  const result = await request(port, '/__bridge/system');
  assert.equal(result.status, 503);
  assert.equal(JSON.parse(result.text).connection, 'BACKEND_ADAPTER_REQUIRED');
  for (const target of ['/__bridge/system/', '/__bridge/system?target=/health', '/__bridge/upload', '/__bridge/clone', '/__bridge/execute', '/__bridge/provider', '/api/v1/system/info']) {
    assert.equal((await request(port, target)).status, 404, target);
  }
});

test('combines only verified real health and system schemas without inventing analysis APIs', async t => {
  const backend = await upstream(t, (incoming, response) => json(response, incoming.url === '/health' ? { status: 'ok' } : SYSTEM));
  const { port } = await fixture(t, { backend: backend.url });
  const result = await request(port, '/__bridge/system');
  assert.equal(result.status, 200);
  assert.deepEqual(JSON.parse(result.text), { connection: 'LIVE_SYSTEM_ONLY', health: { status: 'ok' }, system: SYSTEM });
  assert.deepEqual(backend.requests.sort(), ['/api/v1/system/info', '/health']);
});

test('invalid schemas, content types, JSON and upstream HTTP errors remain explicit failures', async t => {
  const cases = [
    { code: 'UPSTREAM_SCHEMA_INVALID', health: { status: 'ready' }, system: SYSTEM },
    { code: 'UPSTREAM_SCHEMA_INVALID', health: { status: 'ok', secret: 'never-return' }, system: SYSTEM },
    { code: 'UPSTREAM_SCHEMA_INVALID', health: { status: 'ok' }, system: { ...SYSTEM, status: 'production' } },
    { code: 'UPSTREAM_SCHEMA_INVALID', health: { status: 'ok' }, system: { ...SYSTEM, version: 42 } },
    { code: 'UPSTREAM_SCHEMA_INVALID', health: { status: 'ok' }, system: { ...SYSTEM, iam_schema_version: '2.0' } },
    { code: 'UPSTREAM_SCHEMA_INVALID', health: { status: 'ok' }, system: { name: 'missing-fields' } },
    { code: 'UPSTREAM_SCHEMA_INVALID', health: { status: 'ok' }, system: { ...SYSTEM, findings: [] } },
    { code: 'UPSTREAM_SCHEMA_INVALID', health: { status: 'ok' }, system: [] },
    { code: 'UPSTREAM_CONTENT_TYPE_INVALID', type: 'text/html', raw: '<html>never-return</html>' },
    { code: 'UPSTREAM_JSON_INVALID', type: 'application/json', raw: '{invalid never-return' },
    { code: 'UPSTREAM_HTTP_ERROR', status: 500 },
  ];
  for (const [index, item] of cases.entries()) {
    await t.test(`${index + 1}: ${item.code}`, async subtest => {
      const backend = await upstream(subtest, (incoming, response) => {
        if (item.status) { json(response, { message: 'never-return' }, item.status); return; }
        if (item.type) { response.writeHead(200, { 'Content-Type': item.type }); response.end(item.raw); return; }
        json(response, incoming.url === '/health' ? item.health : item.system);
      });
      const { port } = await fixture(subtest, { backend: backend.url });
      const result = await request(port, '/__bridge/system');
      assert.equal(result.status, 502);
      assert.equal(JSON.parse(result.text).error, item.code);
      assert.equal(JSON.parse(result.text).connection, 'BACKEND_UNAVAILABLE');
      assert.doesNotMatch(result.text, /never-return|missing-fields|"health"|"system"/);
    });
  }
});

test('redirects are not followed', async t => {
  const backend = await upstream(t, (_incoming, response) => {
    response.writeHead(302, { Location: 'http://127.0.0.1:1/untrusted-target' });
    response.end();
  });
  const { port } = await fixture(t, { backend: backend.url });
  const result = await request(port, '/__bridge/system');
  assert.equal(result.status, 502);
  assert.equal(JSON.parse(result.text).error, 'UPSTREAM_REDIRECT_REJECTED');
  assert.ok(backend.requests.every(target => ['/health', '/api/v1/system/info'].includes(target)));
});

test('enforces 64 KiB response ceiling with and without Content-Length', async t => {
  for (const declared of [false, true]) {
    await t.test(declared ? 'declared length' : 'chunked body', async subtest => {
      const backend = await upstream(subtest, (_incoming, response) => {
        response.writeHead(200, { 'Content-Type': 'application/json', ...(declared ? { 'Content-Length': 65537 } : {}) });
        response.end('x'.repeat(65537));
      });
      const { port } = await fixture(subtest, { backend: backend.url });
      const result = await request(port, '/__bridge/system');
      assert.equal(result.status, 502);
      assert.equal(JSON.parse(result.text).error, 'UPSTREAM_RESPONSE_TOO_LARGE');
    });
  }
});

test('bounds total upstream time and reports connection failure without raw exception data', async t => {
  const backend = await upstream(t, (_incoming, _response) => {});
  const { port } = await fixture(t, { backend: backend.url, timeoutMs: 40 });
  const result = await request(port, '/__bridge/system');
  assert.equal(result.status, 504);
  assert.equal(JSON.parse(result.text).error, 'UPSTREAM_TIMEOUT');
  const unused = http.createServer();
  const unavailablePort = await listen(unused);
  await close(unused);
  const failed = await fixture(t, { backend: `http://127.0.0.1:${unavailablePort}` });
  const failure = await request(failed.port, '/__bridge/system');
  assert.equal(failure.status, 502);
  assert.equal(JSON.parse(failure.text).error, 'UPSTREAM_UNAVAILABLE');
  assert.doesNotMatch(failure.text, /ECONNREFUSED|127\.0\.0\.1|stack/);
});
