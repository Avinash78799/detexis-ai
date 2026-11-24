const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const {join} = require('node:path');

test('dashboard warns on failed refresh, recovers after swap, and retries', () => {
  const listeners = {};
  const feed = {contains: () => false, querySelector: () => null};
  const status = {dataset: {}, textContent: ''};
  const updated = {};
  let click, retried = false;
  const nodes = {'feed': feed, 'feed-status': status, 'feed-updated': updated,
    'pause-feed': {addEventListener() {}},
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
    assert.equal(status.textContent, 'Automatic updates on.');
    assert.match(updated.textContent, /UTC/);
  }
  listeners['htmx:responseError']({detail: {elt: feed, xhr: {status: 401}}});
  assert.match(status.textContent, /session expired/);
  listeners['htmx:afterSwap']({detail: {elt: {}}});
  assert.equal(status.dataset.state, 'error');
  click();
  assert.equal(retried, true);
});

test('dashboard preserves feed focus and open details, including during an in-flight poll', () => {
  const handlers = {};
  let focused = false;
  let detailsOpen = false;
  const feed = {contains: () => focused, querySelector: () => detailsOpen ? {} : null};
  const status = {dataset: {}, textContent: ''};
  const button = id => ({addEventListener: (_, fn) => {handlers[id] = fn;}});
  const pause = button('pause');
  const nodes = {'feed': feed, 'feed-status': status, 'feed-updated': {},
    'pause-feed': pause, 'refresh-feed': button('refresh')};
  function prevented(name, xhr) {
    let cancelled = false;
    handlers[name]({detail: {elt: feed, target: feed, xhr, shouldSwap: true},
      preventDefault() {cancelled = true;}});
    return cancelled;
  }
  const manualRequest = {};
  runInNewContext(readFileSync(join(__dirname, '../backend/app/static/dashboard.js'), 'utf8'), {
    document: {getElementById: id => nodes[id], body: {addEventListener: (name, fn) => {handlers[name] = fn;}}},
    window: {htmx: {trigger: () => assert.equal(prevented('htmx:beforeRequest', manualRequest), false)}},
  });
  const poll = {};
  assert.equal(prevented('htmx:beforeRequest', poll), false);
  focused = true;
  assert.equal(prevented('htmx:beforeSwap', poll), true);
  assert.equal(prevented('htmx:beforeRequest', {}), true);
  focused = false;
  detailsOpen = true;
  assert.equal(prevented('htmx:beforeSwap', poll), true);
  assert.equal(prevented('htmx:beforeRequest', {}), true);
  detailsOpen = false;
  handlers.pause();
  assert.equal(pause.textContent, 'Resume automatic updates');
  assert.equal(prevented('htmx:beforeRequest', {}), true);
  assert.equal(prevented('htmx:beforeSwap', poll), true);
  handlers.refresh();
  assert.equal(prevented('htmx:beforeSwap', manualRequest), false);
  handlers.pause();
  assert.equal(prevented('htmx:beforeRequest', {}), false);
});
