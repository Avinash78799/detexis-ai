const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const {join} = require('node:path');
const settled = () => new Promise(resolve => setImmediate(resolve));

async function workspace(handler) {
  const nodes = new Map(), created = [], calls = [];
  function element() {
    return {children:[], attrs:{}, handlers:{}, textContent:'', disabled:false,
      classList:{add(){},remove(){}}, scrollIntoView(){}, querySelectorAll:()=>[],
      querySelector:()=>({focus(){}}), reset(){},
      setAttribute(k,v){this.attrs[k] = v;},
      addEventListener(k,v){this.handlers[k] = v;},
      append(...items){this.children.push(...items);},
      replaceChildren(...items){this.textContent = ''; this.children = items;},
      remove(){this.removed = true;}};
  }
  const get = id => {if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id);};
  runInNewContext(readFileSync(join(__dirname, '../backend/app/static/account.js'), 'utf8'), {
    document:{getElementById:get, querySelector:get, createElement:()=>{
      const item = element(); created.push(item); return item;
    }},
    location:{protocol:'https:', search:'', origin:'https://localhost:8443'}, URLSearchParams,
    FormData:class { *[Symbol.iterator]() {} },
    window:{shieldApi:async (path,body) => {
      calls.push({path,body});
      if (path === 'session') return {csrf_token:'fixture', email:'fixture@example.test'};
      if (path === 'sites') return [{id:'a',domain:'first.example'}, {id:'b',domain:'second.example'}];
      return handler(path,body);
    }},
  });
  await settled();
  return {get, created, calls, named:name=>created.find(e=>e.attrs['aria-label'] === name)};
}

test('site actions have distinct names and connection panels expose loading, failure and retry', async () => {
  let reject, succeed = false;
  const app = await workspace(() => succeed ? {
    active_key:true, heartbeat:'waiting', latest_event_processing:'waiting', checked_at:'2026-11-22T00:00:00Z',
  } : new Promise((resolve,no)=>{reject = no;}));
  for (const site of ['first.example','second.example']) {
    assert.ok(app.named('Open dashboard for '+site));
    assert.ok(app.named('Manage sensor keys for '+site));
    assert.ok(app.named('Verify domain & scan for '+site));
  }
  const button = app.named('Check sensor connection for second.example');
  const panel = app.named('Sensor connection for second.example');
  assert.equal(panel.hidden, true);
  assert.equal(button.attrs['aria-controls'], panel.id);
  const pending = button.handlers.click();
  assert.equal(button.disabled, true);
  assert.equal(panel.hidden, false);
  assert.equal(panel.attrs['aria-busy'], 'true');
  assert.equal(button.attrs['aria-expanded'], 'true');
  assert.match(panel.textContent, /Checking/);
  reject(new Error('Temporarily unavailable')); await pending;
  assert.equal(button.disabled, false);
  assert.equal(panel.attrs['aria-busy'], 'false');
  assert.match(panel.textContent, /Temporarily unavailable/);
  succeed = true; await button.handlers.click();
  assert.equal(panel.textContent, '');
  assert.equal(panel.children[1].children.length, 3);
  assert.equal(app.calls.filter(x=>x.path.endsWith('/connection')).every(x=>x.path==='sites/b/connection'), true);
});

test('key feedback identifies its site while the private key stays outside live announcements', async () => {
  const secret = 'dxs_fixture_test-only-secret';
  const app = await workspace((path,body) => body ? {api_key:secret} : []);
  const manage = app.named('Manage sensor keys for first.example');
  await manage.handlers.click();
  const panel = app.named('Sensor keys for first.example');
  assert.equal(manage.attrs['aria-controls'], panel.id);
  assert.equal(panel.attrs['aria-live'], undefined);
  const create = app.named('Create replacement key for first.example');
  await create.handlers.click();
  assert.equal(create.removed, true);
  assert.match(app.get('issued-keys-list').children.at(-1).children[1].textContent, /test-only-secret/);
  const live = app.created.filter(x=>x.attrs['aria-live']);
  assert.equal(live.some(x=>x.textContent.includes(secret)), false);
  assert.equal(live.some(x=>x.textContent.includes('Replacement key created')), true);
});

test('a failed key-list request announces the affected site and permits retry', async () => {
  let reject, succeed = false;
  const app = await workspace(() => succeed ? [] : new Promise((resolve,no)=>{reject = no;}));
  const manage = app.named('Manage sensor keys for second.example');
  const pending = manage.handlers.click();
  assert.equal(manage.disabled, true);
  assert.ok(app.created.some(x=>x.attrs.role==='status' && /Loading sensor keys for second.example/.test(x.textContent)));
  reject(new Error('Service unavailable')); await pending;
  assert.equal(manage.disabled, false);
  assert.ok(app.created.some(x=>x.attrs.role==='status' && /could not be loaded for second.example/.test(x.textContent)));
  succeed = true; await manage.handlers.click();
  assert.ok(app.created.some(x=>x.attrs.role==='status' && x.textContent==='0 sensor keys for second.example'));
  assert.equal(manage.disabled, false);
});

test('replacement key remains available when website cards refresh during issuance', async () => {
  let issue;
  const app = await workspace((path, body) => body
    ? new Promise(resolve => {issue = resolve;}) : []);
  await app.named('Manage sensor keys for second.example').handlers.click();
  const creating = app.named('Create replacement key for second.example').handlers.click();
  await app.get('refresh-sites').handlers.click();
  issue({api_key:'dxs_fixture_refresh-only-secret'});
  await creating;
  assert.equal(app.get('issued-keys').hidden, false);
  const text = item => [item.textContent, ...item.children.map(text)].join(' ');
  assert.match(text(app.get('issued-keys-list')), /second\.example/);
  assert.match(text(app.get('issued-keys-list')), /dxs_fixture_refresh-only-secret/);
  await app.get('refresh-sites').handlers.click();
  assert.match(text(app.get('issued-keys-list')), /dxs_fixture_refresh-only-secret/);
  assert.equal(app.created.filter(x=>x.attrs['aria-live']).some(x=>text(x).includes('refresh-only-secret')), false);
});

test('issuing a key for another site preserves both one-time credentials with their hostnames', async () => {
  const app = await workspace((path, body) => body
    ? {api_key:path.includes('/a/') ? 'dxs_first_synthetic' : 'dxs_second_synthetic'} : []);
  for (const name of ['first.example', 'second.example']) {
    await app.named('Manage sensor keys for ' + name).handlers.click();
    await app.named('Create replacement key for ' + name).handlers.click();
  }
  const rows = app.get('issued-keys-list').children;
  assert.equal(rows.length, 2);
  assert.equal(rows[0].children[0].textContent, 'first.example');
  assert.match(rows[0].children[1].textContent, /dxs_first_synthetic/);
  assert.equal(rows[1].children[0].textContent, 'second.example');
  assert.match(rows[1].children[1].textContent, /dxs_second_synthetic/);
  assert.equal(app.get('issued-keys-status').textContent.includes('dxs_'), false);
});

test('a late key response cannot restore credentials after confirmed account deletion', async () => {
  let issue;
  const app = await workspace((path, body) => {
    if (path === 'account/delete') return {};
    return body ? new Promise(resolve=>{issue = resolve;}) : [];
  });
  await app.named('Manage sensor keys for first.example').handlers.click();
  const creating = app.named('Create replacement key for first.example').handlers.click();
  const form = app.get('delete-account-form');
  await form.handlers.submit({preventDefault(){},target:form});
  issue({api_key:'dxs_fixture_late-secret'}); await creating;
  assert.equal(app.get('workspace').hidden, true);
  assert.equal(app.get('issued-keys').hidden, true);
  assert.equal(app.get('issued-keys-list').children.length, 0);
  assert.equal(app.get('issued-keys-status').textContent, '');
});
