const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const {join} = require('node:path');
const settled = () => new Promise(resolve => setImmediate(resolve));
const detail = domain => ({domain,severity:'low',rules:[],event_count:1,status:'open',evidence:[],actions:[]});
const deferred = () => {let resolve, reject; const promise = new Promise((a,b)=>{resolve=a;reject=b;}); return {promise,resolve,reject};};

async function inbox(handler, loadHandler) {
  const nodes = new Map(), calls = [];
  function element() {return {textContent:'',value:'',disabled:false,children:[],handlers:{},
    append(...items){this.children.push(...items);}, replaceChildren(){this.children=[];},
    addEventListener(k,v){this.handlers[k]=v;},scrollIntoView(){}};}
  const get = id => {if (!nodes.has(id)) nodes.set(id,element()); return nodes.get(id);};
  get('triage').querySelectorAll = () => [get('save'),get('status'),get('note')];
  const context = {document:{getElementById:get,createElement:element},
    location:{search:''}, URLSearchParams,
    window:{shieldApi:async (path,body)=>{
      calls.push({path,body});
      if (path==='session') return {csrf_token:'fixture'};
      if (path==='inbox') return loadHandler ? loadHandler() : {incidents:[],next:null};
      return handler(path,body);
    }}};
  runInNewContext(readFileSync(join(__dirname,'../backend/app/static/inbox.js'),'utf8'),context);
  await settled();
  return {get,calls,show:context.show,save:()=>get('triage').handlers.submit({preventDefault(){},target:get('triage')})};
}

test('a committed decision remains reported as saved when detail refresh fails', async () => {
  let reads=0;
  const app = await inbox((path,body)=>{
    if (body) return {};
    if (++reads===1) return detail('first.example');
    throw new Error('Refresh unavailable');
  });
  await app.show('a'); app.get('note').value='reviewed';
  await app.save();
  assert.match(app.get('message').textContent,/Decision saved, but/);
  assert.equal(app.get('note').value,'');
  assert.equal(app.get('save').disabled,false);
  assert.equal(app.calls.filter(c=>c.body).length,1,'no mutation retry after successful commit');
});

test('a rejected or uncertain mutation preserves the draft and does not retry', async () => {
  const app = await inbox((path,body)=>{if (body) throw new Error('Outcome uncertain; check history'); return detail('first.example');});
  await app.show('a'); app.get('note').value='keep draft';
  await app.save();
  assert.equal(app.get('note').value,'keep draft');
  assert.match(app.get('message').textContent,/Outcome uncertain/);
  assert.equal(app.calls.filter(c=>c.body).length,1);
  assert.equal(app.get('status').disabled,false);
});

test('an inbox-list refresh failure cannot turn a saved decision into a save failure', async () => {
  let lists=0;
  const app = await inbox((path,body)=>body ? {} : detail('first.example'),()=>{
    if (++lists>1) throw new Error('Inbox refresh unavailable');
    return {incidents:[],next:null};
  });
  await app.show('a'); await app.save();
  assert.match(app.get('message').textContent,/Decision saved, but/);
  assert.match(app.get('message').textContent,/Inbox refresh unavailable/);
  assert.equal(app.calls.filter(c=>c.body).length,1);
});

test('an obsolete detail failure does not replace the newer selected incident', async () => {
  const old=deferred();
  const app=await inbox(path=>path==='incidents/a' ? old.promise : detail('second.example'));
  const first=app.show('a');
  await app.show('b');
  old.reject(new Error('Obsolete detail failure')); await first;
  assert.equal(app.get('detail-title').textContent,'second.example · low');
  assert.equal(app.get('message').textContent,'');
});

test('pending details cannot switch the selected incident during a save', async () => {
  const oldDetail=deferred(), mutation=deferred();
  const app = await inbox((path,body)=>body ? mutation.promise : path==='incidents/b' ? oldDetail.promise : detail('first.example'));
  await app.show('a');
  const old=app.show('b'); app.get('note').value='first incident';
  const saving=app.save();
  assert.equal(app.get('status').disabled,true);
  assert.equal(app.get('note').disabled,true);
  await app.show('c');
  assert.equal(app.calls.some(c=>c.path==='incidents/c'),false);
  oldDetail.resolve(detail('obsolete.example')); await old;
  assert.equal(app.get('detail-title').textContent,'first.example · low');
  mutation.resolve({}); await saving;
  assert.equal(app.calls.find(c=>c.body).path,'incidents/a/status');
  assert.equal(app.get('message').textContent,'Decision saved.');
});
