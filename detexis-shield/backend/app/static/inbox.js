"use strict";
const el = id => document.getElementById(id);
let csrf = '', cursor = null, selected = null;
let detailRequest = 0, saving = false;
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
    card.append(text('h2',incident.domain), text('p',incident.severity.toUpperCase() + ' Â· ' + statuses[incident.status] + ' Â· ' + incident.event_count + ' matching events'), text('p',incident.rules.join(', ')), text('p','Last seen: ' + incident.last_seen));
    const open = text('button','Investigate'); open.className = 'secondary';
    open.addEventListener('click', () => show(incident.id).catch(error => el('message').textContent = error.message));
    card.append(open); el('inbox').append(card);
  }
  cursor = result.next; el('more').hidden = !cursor;
}
async function show(id, afterSave = false) {
  if (saving && !afterSave) {
    el('message').textContent = 'A decision is being saved. Wait before opening another incident.';
    return;
  }
  const request = ++detailRequest;
  let data;
  try {data = await api('incidents/' + encodeURIComponent(id));}
  catch (error) {if (request !== detailRequest) return; throw error;}
  if (request !== detailRequest) return;
  selected = id;
  el('detail').hidden = false; el('detail-title').textContent = data.domain + ' Â· ' + data.severity;
  el('detail-summary').textContent = data.rules.join(', ') + ' Â· ' + data.event_count + ' matching events';
  el('status').value = data.status; el('note').value = '';
  el('evidence').replaceChildren();
  for (const event of data.evidence) {
    const item = document.createElement('article'); item.className = 'incident';
    item.append(text('strong',event.method + ' ' + event.path), text('p',event.ts + ' Â· HTTP ' + event.status));
    for (const finding of event.findings) item.append(text('p',finding.rule_id + ' Â· ' + finding.cwe + ' Â· ' + finding.owasp + ' â€” ' + finding.reason));
    el('evidence').append(item);
  }
  if (!data.evidence.length) el('evidence').append(text('p','Evidence is unavailable or has expired under retention.'));
  el('history').replaceChildren();
  for (const action of data.actions) el('history').append(text('p', action.at + ' Â· ' + action.actor + ' Â· ' + action.previous_status + ' â†’ ' + action.status + (action.note ? '\n' + action.note:'')));
  if (!data.actions.length) el('history').append(text('p','No review decisions recorded yet.'));
  el('detail').scrollIntoView({block:'start'});
}
el('triage').addEventListener('submit', async event => {
  event.preventDefault();
  if (saving) return;
  if (!selected) {el('message').textContent = 'Open an incident before saving a decision.'; return;}
  const id = selected, body = {status:el('status').value,note:el('note').value};
  const fields = [...event.target.querySelectorAll('button, select, textarea')];
  const previous = fields.map(field => field.disabled);
  fields.forEach(field => field.disabled = true);
  saving = true; ++detailRequest;
  let committed = false;
  el('message').textContent = 'Saving decisionâ€¦';
  try {
    await api('incidents/' + encodeURIComponent(id) + '/status', body);
    committed = true; el('note').value = '';
    await show(id, true); await load();
    el('message').textContent = 'Decision saved.';
  } catch(error) {
    el('message').textContent = committed
      ? 'Decision saved, but the view could not be refreshed. Refresh the inbox before making another decision. ' + error.message
      : error.message;
  } finally {
    saving = false;
    fields.forEach((field, index) => field.disabled = previous[index]);
  }
});
for (const [id, reset] of [['refresh',true],['more',false]]) el(id).addEventListener('click', async () => {el(id).disabled = true; try {await load(reset);} catch(error) {el('message').textContent = error.message;} finally {el(id).disabled = false;}});
api('session').then(async data => {
  csrf = data.csrf_token; await load();
  const incident = new URLSearchParams(location.search).get('incident');
  if (incident) await show(incident);
}).catch(error => el('message').textContent = error.message);
