const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const {join} = require('node:path');

function workspace({signedIn = true} = {}) {
  const nodes = new Map(), calls = [];
  let failSites = true;
  const get = id => {
    if (!nodes.has(id)) nodes.set(id, {
      hidden: id === 'workspace', disabled:false, textContent:'', children:[], handlers:{},
      classList:{add(){}}, addEventListener(name, fn){this.handlers[name] = fn;},
      querySelectorAll:()=>[], scrollIntoView(){},
      reset(){this.resetCalled = true;}, append(...items){this.children.push(...items);},
      replaceChildren(){this.children = [];},
    });
    return nodes.get(id);
  };
  runInNewContext(readFileSync(join(__dirname, '../backend/app/static/account.js'), 'utf8'), {
    document:{getElementById:get, querySelector:get, createElement:()=>({append(){}})},
    location:{protocol:'https:', search:'', origin:'https://localhost:8443'}, URLSearchParams,
    FormData:class { *[Symbol.iterator](){yield ['password', 'synthetic-password'];} },
    window:{shieldApi:async path => {
      calls.push(path);
      if (path === 'session' && !signedIn) throw Object.assign(new Error('signed out'), {status:401});
      if (path === 'sites') {
        if (failSites) throw new Error('Service temporarily unavailable');
        return [];
      }
      return {csrf_token:'test-csrf', email:'fixture@example.invalid', recovery_code:'test-only-recovery'};
    }},
  });
  return {get, calls, succeed(){failSites = false;}};
}

// Let the session -> workspace -> sites -> catch promise chain settle.
const settled = () => new Promise(resolve => setImmediate(resolve));

test('site-list outage preserves the authenticated workspace and allows an explicit retry', async () => {
  const app = workspace();
  app.get('sites').children.push('previous site card');
  await settled();
  assert.equal(app.get('workspace').hidden, false);
  assert.equal(app.get('auth').hidden, true);
  assert.equal(app.get('recovery-value').textContent, 'test-only-recovery');
  assert.deepEqual(app.get('sites').children, ['previous site card']);
  assert.match(app.get('sites-status').textContent, /may be out of date/);
  assert.match(app.get('sites-status').textContent, /Refresh websites/);
  assert.equal(app.calls.filter(path => path === 'sites').length, 1, 'no automatic retry loop');
  app.succeed();
  const retry = app.get('refresh-sites').handlers.click();
  assert.equal(app.get('refresh-sites').disabled, true);
  await retry;
  assert.equal(app.get('refresh-sites').disabled, false);
  assert.equal(app.get('sites').children.length, 1, 'empty-state replaces stale cards');
  assert.equal(app.get('sites-status').textContent, '');
  assert.equal(app.get('recovery-value').textContent, 'test-only-recovery');
});

test('successful registration clears submitted credentials even when the website list fails', async () => {
  const app = workspace({signedIn:false});
  await settled();
  const form = app.get('auth-form');
  await form.handlers.submit({preventDefault(){}, target:form, submitter:{value:'register'}});
  assert.equal(form.resetCalled, true);
  assert.equal(app.get('auth').hidden, true);
  assert.equal(app.get('workspace').hidden, false);
  assert.equal(app.get('recovery-secret').hidden, false);
  assert.equal(app.get('recovery-value').textContent, 'test-only-recovery');
  assert.match(app.get('sites-status').textContent, /could not be refreshed/);
  assert.equal(app.get('message').textContent, '', 'list failure is not reported as an auth failure');
  await app.get('refresh-sites').handlers.click();
  assert.equal(app.get('refresh-sites').disabled, false, 'failed retry remains usable');
});
