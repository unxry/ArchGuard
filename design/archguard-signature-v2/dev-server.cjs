'use strict';

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const net = require('node:net');

const MAX_RESPONSE_BYTES = 64 * 1024;
const MIME = Object.freeze({
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.ico': 'image/x-icon',
  '.md': 'text/plain; charset=utf-8', '.txt': 'text/plain; charset=utf-8',
});

function validateBackend(value) {
  if (value == null || value === '') return null;
  if (typeof value !== 'string') throw new Error('BACKEND_URL_INVALID');
  const match = /^http:\/\/(127(?:\.\d{1,3}){3}|\[::1\])(?::(\d{1,5}))?\/?$/.exec(value);
  if (!match) throw new Error('BACKEND_URL_INVALID');
  const hostname = match[1].replace(/^\[|\]$/g, '');
  if (!net.isIP(hostname) || (match[2] && (+match[2] < 1 || +match[2] > 65535))) {
    throw new Error('BACKEND_URL_INVALID');
  }
  return new URL(value);
}

function exactObject(value, fields) {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).length === fields.length
    && fields.every(field => Object.prototype.hasOwnProperty.call(value, field));
}

function validateSystem(health, system) {
  if (!exactObject(health, ['status']) || health.status !== 'ok'
    || !exactObject(system, ['name', 'version', 'status', 'iam_schema_version', 'finding_schema_version'])
    || typeof system.name !== 'string' || typeof system.version !== 'string'
    || system.status !== 'foundation' || system.iam_schema_version !== '1.0'
    || system.finding_schema_version !== '1.0') {
    throw new Error('UPSTREAM_SCHEMA_INVALID');
  }
}

function upstreamJSON(base, pathname, timeoutMs) {
  return new Promise((resolve, reject) => {
    let finished = false;
    let request;
    let timer;
    function fail(code) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      reject(new Error(code));
      request?.destroy();
    }
    request = http.get(new URL(pathname, base), {
      headers: { Accept: 'application/json' }, agent: false,
    }, response => {
      if (response.statusCode >= 300 && response.statusCode < 400) {
        fail('UPSTREAM_REDIRECT_REJECTED'); return;
      }
      if (response.statusCode !== 200) { fail('UPSTREAM_HTTP_ERROR'); return; }
      if (!/^application\/json(?:\s*;|$)/i.test(response.headers['content-type'] || '')) {
        fail('UPSTREAM_CONTENT_TYPE_INVALID'); return;
      }
      if (Number(response.headers['content-length']) > MAX_RESPONSE_BYTES) {
        fail('UPSTREAM_RESPONSE_TOO_LARGE'); return;
      }
      let size = 0;
      const chunks = [];
      response.on('data', chunk => {
        if (finished) return;
        size += chunk.length;
        if (size > MAX_RESPONSE_BYTES) { fail('UPSTREAM_RESPONSE_TOO_LARGE'); return; }
        chunks.push(chunk);
      });
      response.on('error', () => fail('UPSTREAM_UNAVAILABLE'));
      response.on('end', () => {
        if (finished) return;
        let value;
        try { value = JSON.parse(Buffer.concat(chunks).toString('utf8')); }
        catch { fail('UPSTREAM_JSON_INVALID'); return; }
        finished = true;
        clearTimeout(timer);
        resolve(value);
      });
    });
    request.on('error', () => fail('UPSTREAM_UNAVAILABLE'));
    timer = setTimeout(() => fail('UPSTREAM_TIMEOUT'), timeoutMs);
    timer.unref();
  });
}

function sendJSON(response, status, body, head = false) {
  const data = Buffer.from(JSON.stringify(body));
  response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Content-Length': data.length });
  response.end(head ? undefined : data);
}

function safeSegments(target) {
  if (typeof target !== 'string' || !target.startsWith('/') || target.startsWith('//') || target.includes('#')) {
    throw new Error('STATIC_PATH_REJECTED');
  }
  const raw = target.split('?')[0];
  if (raw === '/') return ['index.html'];
  return raw.slice(1).split('/').map(segment => {
    let decoded;
    try { decoded = decodeURIComponent(segment); } catch { throw new Error('STATIC_PATH_REJECTED'); }
    if (!decoded || decoded.startsWith('.') || /[\\/\x00-\x1f\x7f%]/.test(decoded)) {
      throw new Error('STATIC_PATH_REJECTED');
    }
    return decoded;
  });
}

async function staticFile(root, target) {
  const segments = safeSegments(target);
  const filename = path.join(root, ...segments);
  if (!MIME[path.extname(filename).toLowerCase()]) throw new Error('STATIC_NOT_FOUND');
  let current = root;
  for (let index = 0; index < segments.length; index++) {
    current = path.join(current, segments[index]);
    const metadata = await fs.promises.lstat(current);
    if (metadata.isSymbolicLink()) throw new Error('STATIC_PATH_REJECTED');
    if (index < segments.length - 1 ? !metadata.isDirectory() : !metadata.isFile()) {
      throw new Error('STATIC_NOT_FOUND');
    }
  }
  const canonical = await fs.promises.realpath(filename);
  if (canonical !== filename || !canonical.startsWith(root + path.sep)) throw new Error('STATIC_PATH_REJECTED');
  const handle = await fs.promises.open(filename, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const metadata = await handle.stat();
    if (!metadata.isFile()) throw new Error('STATIC_NOT_FOUND');
    return { handle, size: metadata.size, type: MIME[path.extname(filename).toLowerCase()] };
  } catch (error) {
    await handle.close();
    throw error;
  }
}

function createDevServer({ root = __dirname, backend = null, timeoutMs = 3000 } = {}) {
  const artifactRoot = fs.realpathSync(root);
  if (!fs.statSync(artifactRoot).isDirectory()) throw new Error('ARTIFACT_ROOT_INVALID');
  const upstream = validateBackend(backend);
  const server = http.createServer((request, response) => {
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Cross-Origin-Resource-Policy', 'same-origin');
    response.setHeader('Referrer-Policy', 'no-referrer');
    response.setHeader('X-Frame-Options', 'DENY');
    const head = request.method === 'HEAD';
    const expectedHost = `127.0.0.1:${server.address().port}`;
    const headerCount = name => request.rawHeaders.filter((item, index) => index % 2 === 0 && item.toLowerCase() === name).length;
    if (request.headers.host !== expectedHost || headerCount('host') !== 1
      || headerCount('origin') > 1
      || (request.headers.origin && request.headers.origin !== `http://${expectedHost}`)) {
      sendJSON(response, 403, { error: 'LOCAL_ORIGIN_REQUIRED' }, head); return;
    }
    if (request.method !== 'GET' && !head) {
      response.setHeader('Allow', 'GET, HEAD');
      sendJSON(response, 405, { error: 'METHOD_NOT_ALLOWED' }); return;
    }
    if (request.headers['transfer-encoding'] || Number(request.headers['content-length'] || 0) !== 0) {
      sendJSON(response, 400, { error: 'REQUEST_BODY_NOT_ALLOWED' }, head); return;
    }
    if (request.url === '/__bridge/system') {
      if (head) {
        response.setHeader('Allow', 'GET');
        sendJSON(response, 405, { error: 'METHOD_NOT_ALLOWED' }, true); return;
      }
      if (!upstream) {
        sendJSON(response, 503, { connection: 'BACKEND_ADAPTER_REQUIRED', error: 'BACKEND_ADAPTER_REQUIRED' }); return;
      }
      Promise.all([upstreamJSON(upstream, '/health', timeoutMs), upstreamJSON(upstream, '/api/v1/system/info', timeoutMs)])
        .then(([health, system]) => {
          validateSystem(health, system);
          sendJSON(response, 200, { connection: 'LIVE_SYSTEM_ONLY', health, system });
        }).catch(error => {
          const allowed = new Set(['UPSTREAM_SCHEMA_INVALID', 'UPSTREAM_REDIRECT_REJECTED', 'UPSTREAM_HTTP_ERROR', 'UPSTREAM_CONTENT_TYPE_INVALID', 'UPSTREAM_RESPONSE_TOO_LARGE', 'UPSTREAM_UNAVAILABLE', 'UPSTREAM_JSON_INVALID', 'UPSTREAM_TIMEOUT']);
          const code = allowed.has(error.message) ? error.message : 'UPSTREAM_UNAVAILABLE';
          sendJSON(response, code === 'UPSTREAM_TIMEOUT' ? 504 : 502, { connection: 'BACKEND_UNAVAILABLE', error: code });
        });
      return;
    }
    if (request.url.startsWith('/__bridge')) { sendJSON(response, 404, { error: 'NOT_FOUND' }, head); return; }
    staticFile(artifactRoot, request.url).then(async file => {
      response.writeHead(200, { 'Content-Type': file.type, 'Content-Length': file.size });
      if (head) { await file.handle.close(); response.end(); return; }
      const stream = file.handle.createReadStream();
      stream.on('error', () => response.destroy());
      response.on('close', () => stream.destroy());
      stream.pipe(response);
    }).catch(error => {
      if (response.headersSent) { response.destroy(); return; }
      const denied = error.message === 'STATIC_PATH_REJECTED' || error.code === 'ELOOP';
      sendJSON(response, denied ? 403 : 404, { error: denied ? 'STATIC_PATH_REJECTED' : 'NOT_FOUND' }, head);
    });
  });
  server.headersTimeout = 5000;
  server.requestTimeout = 5000;
  server.maxHeadersCount = 32;
  return server;
}

function parseArguments(args) {
  const options = { port: 8779, backend: null };
  const seen = new Set();
  for (let index = 0; index < args.length; index += 2) {
    const flag = args[index], value = args[index + 1];
    if (!['--port', '--backend'].includes(flag) || value === undefined || seen.has(flag)) {
      throw new Error('Usage: node dev-server.cjs [--port 8779] [--backend http://127.0.0.1:8780]');
    }
    seen.add(flag);
    if (flag === '--port') {
      if (!/^\d+$/.test(value) || +value < 1 || +value > 65535) throw new Error('PORT_INVALID');
      options.port = +value;
    } else { validateBackend(value); options.backend = value; }
  }
  return options;
}

if (require.main === module) {
  try {
    const options = parseArguments(process.argv.slice(2));
    const server = createDevServer(options);
    server.on('error', () => { process.stderr.write('DEV_SERVER_START_FAILED\n'); process.exitCode = 1; });
    server.listen(options.port, '127.0.0.1', () => {
      process.stdout.write(`ArchGuard signature v2: http://127.0.0.1:${options.port}\n`);
      process.stdout.write(`System bridge: ${options.backend ? 'configured; system endpoints only' : 'BACKEND_ADAPTER_REQUIRED'}\n`);
    });
  } catch (error) {
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}

module.exports = { createDevServer, validateBackend, parseArguments };
