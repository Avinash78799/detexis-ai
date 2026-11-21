const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const {join} = require('node:path');

test('dashboard warns on failed refresh, recovers after swap, and retries', () => {
  const listeners = {};
  const feed = {};
  const status = {dataset: {}, textContent: ''};
  let click, retried = false;
  const nodes = {'feed': feed, 'feed-status': status,
    'refresh-feed': {addEventListener: (_, fn) => {click = fn;}}};
  runInNewContext(readFileSync(join(__dirname, '../backend/app/static/dashboard.js'), 'utf8'), {
    document: {getElementById: id => nodes[id], body: {addEventListener: (name, fn) => {listeners[name] = fn;}}},
    window: {htmx: {trigger: (target, name) => {assert.equal(target, feed); assert.equal(name, 'refresh'); retried = true;}}},
  });
  for (const name of ['htmx:responseError', 'htmx:sendError', 'htmx:timeout']) {
    listeners[name]({detail: {elt: feed, xhr: {status: 503}}});
    assert.equal(status.dataset.state, 'error');
    assert.match(status.textContent, /may be outdated/);
    listeners['htmx:afterSwap']({detail: {elt: feed}});
    assert.equal(status.dataset.state, 'ok');
    assert.match(status.textContent, /UTC/);
  }
  listeners['htmx:responseError']({detail: {elt: feed, xhr: {status: 401}}});
  assert.match(status.textContent, /session expired/);
  listeners['htmx:afterSwap']({detail: {elt: {}}});
  assert.equal(status.dataset.state, 'error');
  click();
  assert.equal(retried, true);
});
