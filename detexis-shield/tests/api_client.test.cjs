const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const {join} = require('node:path');

function client(fetch) {
  let timeout, cleared = false;
  const context = {window: {}, fetch, AbortController,
    setTimeout: fn => {timeout = fn; return 1;},
    clearTimeout: () => {cleared = true;}};
  runInNewContext(readFileSync(join(__dirname, '../backend/app/static/api.js'), 'utf8'), context);
  return {request: context.window.shieldApi, expire: () => timeout(), cleared: () => cleared};
}
const response = (status, data) => ({status, ok: status >= 200 && status < 300, json: async () => data});

test('requests retain CSRF and same-origin credentials and handle empty logout', async () => {
  const api = client(async (url, options) => {
    assert.equal(url, '/app/api/logout');
    assert.equal(options.method, 'POST');
    assert.equal(options.credentials, 'same-origin');
    assert.equal(options.headers['X-CSRF-Token'], 'test-csrf');
    return response(204);
  });
  assert.equal(Object.keys(await api.request('logout', {}, 'test-csrf')).length, 0);
  assert.equal(api.cleared(), true);
});

test('server HTML and malformed responses produce useful errors', async () => {
  const down = client(async () => ({status: 503, json: async () => {throw new Error('html');}}));
  await assert.rejects(down.request('sites'), /temporarily unavailable/);
  const malformed = client(async () => ({status: 200, ok: true, json: async () => {throw new Error('html');}}));
  await assert.rejects(malformed.request('sites'), /unexpected response/);
});

test('session expiry differs from rejected sign-in credentials', async () => {
  const api = client(async () => response(401, {detail: 'Invalid credentials'}));
  await assert.rejects(api.request('sites'), /session expired/);
  await assert.rejects(api.request('login', {}), /Invalid credentials/);
});

test('timed-out mutations warn about uncertain completion and are not retried', async () => {
  let calls = 0;
  const api = client((url, options) => {
    calls++;
    return new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new Error('aborted'))));
  });
  const pending = api.request('sites', {domain: 'synthetic.example'});
  api.expire();
  await assert.rejects(pending, /may have completed; refresh before retrying/);
  assert.equal(calls, 1);
  assert.equal(api.cleared(), true);
});

test('network failures and rate limits remain actionable', async () => {
  const offline = client(async () => {throw new Error('network');});
  await assert.rejects(offline.request('sites'), /Check your connection/);
  const limited = client(async () => response(429, {detail: 'Please wait before trying again'}));
  await assert.rejects(limited.request('sites'), /Please wait/);
});
