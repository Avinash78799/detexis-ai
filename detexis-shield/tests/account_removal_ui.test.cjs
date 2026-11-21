const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const {join} = require('node:path');

async function runDeletion(failure) {
  const nodes = new Map(), fields = [{disabled:false}, {disabled:true}], calls = [];
  const get = id => {
    if (!nodes.has(id)) nodes.set(id, {hidden:false, textContent:'private fixture', handlers:{},
      addEventListener(name, handler) {this.handlers[name] = handler;},
      querySelectorAll:()=>fields, querySelector:()=>({focus(){}}),
      reset(){this.resetCalled = true;}, replaceChildren(){this.cleared = true;},
      classList:{remove(){}}});
    return nodes.get(id);
  };
  runInNewContext(readFileSync(join(__dirname, '../backend/app/static/account.js'), 'utf8'), {
    document:{getElementById:get, querySelector:get}, location:{protocol:'https:'},
    FormData: class {
      constructor() {assert.equal(fields[0].disabled, false, 'read credentials before disabling inputs');}
      *[Symbol.iterator]() {yield ['password','synthetic-current-password']; yield ['confirmation','DELETE'];}
    },
    window:{shieldApi:async (path, body)=>{
      if (path === 'session') throw Object.assign(new Error('signed out'), {status:401});
      calls.push({path, body});
      if (failure) throw new Error('Password is incorrect');
      return {};
    }},
  });
  await Promise.resolve(); await Promise.resolve();
  await get('delete-account-form').handlers.submit({preventDefault(){}, target:get('delete-account-form')});
  return {get, fields, calls};
}

test('confirmed removal clears secrets and workspace only after server success', async () => {
  const {get, fields, calls} = await runDeletion(false);
  assert.equal(calls.length, 1); assert.equal(calls[0].path, 'account/delete');
  assert.equal(calls[0].body.password, 'synthetic-current-password');
  assert.equal(calls[0].body.confirmation, 'DELETE');
  assert.equal(get('workspace').hidden, true); assert.equal(get('auth').hidden, false);
  for (const id of ['credentials','snippet','recovery-value','owner-email']) assert.equal(get(id).textContent, '');
  assert.equal(get('sites').cleared, true);
  for (const id of ['auth-form','site-form','recovery-form','password-form','recover-form']) assert.equal(get(id).resetCalled, true);
  assert.equal(get('delete-account-form').resetCalled, true);
  assert.deepEqual(fields.map(x=>x.disabled), [false,true]);
});

test('rejected removal preserves workspace and explains password error', async () => {
  const {get, fields} = await runDeletion(true);
  assert.equal(get('workspace').hidden, false);
  assert.equal(get('credentials').textContent, 'private fixture');
  assert.equal(get('delete-status').textContent, 'Password is incorrect');
  assert.equal(get('delete-account-form').resetCalled, true);
  assert.deepEqual(fields.map(x=>x.disabled), [false,true]);
});
