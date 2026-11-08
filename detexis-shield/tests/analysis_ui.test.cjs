const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const {join} = require('node:path');

async function screen(analysis) {
  const nodes = new Map(), calls = [];
  function node() {
    return {textContent:'', hidden:true, dataset:{}, children:[], handlers:{}, fieldset:{disabled:true},
      append(...items) {this.children.push(...items);},
      replaceChildren(...items) {this.children = items;},
      querySelector() {return this.fieldset;},
      addEventListener(event, callback) {this.handlers[event] = callback;},
      set innerHTML(_) {throw new Error('Untrusted findings must render as text');}};
  }
  const get = id => {if (!nodes.has(id)) nodes.set(id, node()); return nodes.get(id);};
  const api = async (path, body, csrf) => {
    if (path === 'session') return {csrf_token:'csrf-fixture'};
    if (path === 'analyze/capabilities') return {file_scan:'configured'};
    calls.push({path, body, csrf}); return analysis(path, body);
  };
  runInNewContext(readFileSync(join(__dirname, '../backend/app/static/analyze.js'), 'utf8'), {
    document:{getElementById:get, createElement:node}, window:{shieldApi:api}, Uint8Array, btoa,
    FormData: class {
      constructor(form) {
        assert.equal(form.fieldset.disabled, false, 'Read values before disabling controls');
        this.values = form.values;
      }
      get(key) {return this.values[key];}
    },
  });
  await new Promise(resolve => setImmediate(resolve));
  async function submit(id, values) {
    const form = get(id); form.values = values;
    await form.handlers.submit({target:form, preventDefault(){}});
  }
  return {get, calls, submit};
}
function content(node) {return node.textContent + node.children.map(content).join(' ');}

test('request analysis submits values and CSRF, renders evidence as text and removes a stale verdict on failure', async () => {
  let attempts = 0;
  const ui = await screen(async () => {
    if (attempts++) throw new Error('Scanner unavailable');
    return {engine:'shield-rules-v1', severity:'high', scope:'One request', limitations:'No proof of compromise',
      findings:[{reason:'<script>untrusted evidence</script>',rule_id:'xss',cwe:'CWE-79',owasp:'A05:2025'}]};
  });
  const values = {path:'/search',query:'q=test',user_agent:'browser',status:'200'};
  await ui.submit('request-form', values);
  assert.equal(ui.calls[0].body.path, '/search');
  assert.equal(ui.calls[0].body.status, 200);
  assert.equal(ui.calls[0].csrf, 'csrf-fixture');
  assert.match(content(ui.get('request-result')), /CWE-79/);
  assert.match(content(ui.get('request-result')), /<script>untrusted evidence<\/script>/);
  assert.equal(ui.get('request-result').hidden, false);
  await ui.submit('request-form', values);
  assert.equal(ui.get('request-result').hidden, true);
  assert.match(ui.get('message').textContent, /unavailable/);
  assert.equal(ui.get('request-form').fieldset.disabled, false);
});

test('file analysis validates size before upload and sends exact bytes, not its filename', async () => {
  const ui = await screen(async () => ({verdict:'no_signature_detected', bytes:3, sha256:'abc', engine:'fixture', limitations:'No signature is not safe'}));
  await ui.submit('file-form', {file:{size:1048577}});
  assert.equal(ui.calls.length, 0);
  assert.match(ui.get('message').textContent, /1 MiB/);
  await ui.submit('file-form', {file:{size:3, name:'private-filename.txt', arrayBuffer:async()=>new Uint8Array([65,66,67]).buffer}});
  assert.equal(ui.calls[0].body.content_base64, 'QUJD');
  assert.deepEqual(Object.keys(ui.calls[0].body), ['content_base64']);
  assert.match(content(ui.get('file-result')), /No signature detected/);
  assert.match(content(ui.get('file-result')), /not safe/);
});
