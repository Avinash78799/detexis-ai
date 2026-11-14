const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const {join} = require('node:path');

test('HTTP workspace explains HTTPS and disables credential entry without requesting a session', () => {
  const fields = [{disabled:false}, {disabled:false}, {disabled:false}];
  const nodes = new Map();
  let requested = false;
  const get = id => {
    if (!nodes.has(id)) nodes.set(id, {textContent:'', addEventListener:()=>{}, querySelectorAll:()=>fields});
    return nodes.get(id);
  };
  runInNewContext(readFileSync(join(__dirname, '../backend/app/static/account.js'), 'utf8'), {
    document: {getElementById:get}, location:{protocol:'http:'},
    window:{shieldApi:()=>{requested=true; throw new Error('must not request');}},
  });
  assert.equal(requested, false);
  assert.match(get('message').textContent, /Account actions require HTTPS/);
  assert.equal(fields.every(field=>field.disabled), true);
});
