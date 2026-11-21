"use strict";
const el = id => document.getElementById(id);
let csrf = '', cursor = null, selected = null;
const statuses = {open:'Open', acknowledged:'Acknowledged', resolved:'Resolved', false_positive:'False positive'};
async function api(path, body) {
  return window.shieldApi(path, body, csrf);
}
function text(tag, content) {const node = document.createElement(tag); node.textContent = content; return node;}
async function load(reset = true) {
  el('message').textContent = '';
  const params = !reset && cursor ? '?' + new URLSearchParams(cursor):'';
  const result = await api('inbox' + params);
  if (reset) el('inbox').replaceChildren();
  if (reset && !result.incidents.length) el('inbox').append(text('p','No incidents yet. Connect a sensor to start monitoring.'));
  for (const incident of result.incidents) {
    const card = document.createElement('article'); card.className = 'account-card';
    card.append(text('h2',incident.domain), text('p',incident.severity.toUpperCase() + ' · ' + statuses[incident.status] + ' · ' + incident.event_count + ' matching events'), text('p',incident.rules.join(', ')), text('p','Last seen: ' + incident.last_seen));
    const open = text('button','Investigate'); open.className = 'secondary';
    open.addEventListener('click', () => show(incident.id).catch(error => el('message').textContent = error.message));
    card.append(open); el('inbox').append(card);
  }
  cursor = result.next; el('more').hidden = !cursor;
}
async function show(id) {
  const data = await api('incidents/' + encodeURIComponent(id)); selected = id;
  el('detail').hidden = false; el('detail-title').textContent = data.domain + ' · ' + data.severity;
  el('detail-summary').textContent = data.rules.join(', ') + ' · ' + data.event_count + ' matching events';
  el('status').value = data.status; el('note').value = '';
  el('evidence').replaceChildren();
  for (const event of data.evidence) {
    const item = document.createElement('article'); item.className = 'incident';
    item.append(text('strong',event.method + ' ' + event.path), text('p',event.ts + ' · HTTP ' + event.status));
    for (const finding of event.findings) item.append(text('p',finding.rule_id + ' · ' + finding.cwe + ' · ' + finding.owasp + ' — ' + finding.reason));
    el('evidence').append(item);
  }
  if (!data.evidence.length) el('evidence').append(text('p','Evidence is unavailable or has expired under retention.'));
  el('history').replaceChildren();
  for (const action of data.actions) el('history').append(text('p', action.at + ' · ' + action.actor + ' · ' + action.previous_status + ' → ' + action.status + (action.note ? '\n' + action.note:'')));
  if (!data.actions.length) el('history').append(text('p','No review decisions recorded yet.'));
  el('detail').scrollIntoView({block:'start'});
}
el('triage').addEventListener('submit', async event => {
  event.preventDefault(); const button = event.target.querySelector('button'); button.disabled = true;
  try {await api('incidents/' + encodeURIComponent(selected) + '/status', {status:el('status').value,note:el('note').value}); await show(selected); await load(); el('message').textContent = 'Decision saved.';}
  catch(error) {el('message').textContent = error.message;} finally {button.disabled = false;}
});
for (const [id, reset] of [['refresh',true],['more',false]]) el(id).addEventListener('click', async () => {el(id).disabled = true; try {await load(reset);} catch(error) {el('message').textContent = error.message;} finally {el(id).disabled = false;}});
api('session').then(async data => {
  csrf = data.csrf_token; await load();
  const incident = new URLSearchParams(location.search).get('incident');
  if (incident) await show(incident);
}).catch(error => el('message').textContent = error.message);
