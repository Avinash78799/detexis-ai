"use strict";
const el = id => document.getElementById(id);
let csrf = '', cursor = null, selected = null;
let detailRequest = 0, listRequest = 0, saving = false, listAction = false;
const statuses = {open:'Open', acknowledged:'Acknowledged', resolved:'Resolved', false_positive:'False positive'};
async function api(path, body) {
  return window.shieldApi(path, body, csrf);
}
function text(tag, content) {const node = document.createElement(tag); node.textContent = content; return node;}
async function load(reset = true) {
  const request = ++listRequest;
  const params = !reset && cursor ? '?' + new URLSearchParams(cursor):'';
  let result;
  try {result = await api('inbox' + params);}
  catch (error) {if (request !== listRequest) return; throw error;}
  if (request !== listRequest) return;
  let firstHeading;
  if (reset) el('inbox').replaceChildren();
  if (reset && !result.incidents.length) el('inbox').append(text('p','No incidents yet. Connect a sensor to start monitoring.'));
  for (const incident of result.incidents) {
    const card = document.createElement('article'); card.className = 'account-card';
    const heading = text('h2',incident.domain);
    firstHeading ??= heading;
    card.append(heading, text('p',incident.severity.toUpperCase() + ' · ' + statuses[incident.status] + ' · ' + incident.event_count + ' matching events'), text('p',incident.rules.join(', ')), text('p','Last seen: ' + incident.last_seen));
    const open = text('button','Investigate'); open.className = 'secondary';
    open.setAttribute('aria-label', 'Investigate incident for ' + incident.domain + ' at ' + incident.last_seen);
    open.setAttribute('aria-controls', 'detail');
    open.addEventListener('click', () => show(incident.id).catch(error => el('message').textContent = error.message));
    card.append(open); el('inbox').append(card);
  }
  cursor = result.next;
  if (document.activeElement === el('more')) {
    if (!reset && firstHeading) {
      firstHeading.tabIndex = -1;
      firstHeading.focus();
    } else if (!cursor) {
      el('refresh').focus();
    }
  }
  el('more').hidden = !cursor;
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
  el('detail').hidden = false; el('detail-title').textContent = data.domain + ' · ' + data.severity;
  el('detail-summary').textContent = data.rules.join(', ') + ' · ' + data.event_count + ' matching events';
  const correlations = {
    recon_to_exploit:'Reconnaissance observed before an exploit indicator',
    recon_and_exploit:'Reconnaissance and exploit indicators observed (order unverified)',
    repeated_login_failures:'Repeated login failures',
    flood:'Request flood',
  };
  for (const label of data.correlations || []) {
    el('detail-summary').append(text('span', ' · ' + (correlations[label] || label.replaceAll('_', ' '))));
  }
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
  if (!afterSave) {
    el('decision-status').textContent = '';
    el('detail').scrollIntoView({block:'start'});
    el('detail-title').tabIndex = -1;
    el('detail-title').focus({preventScroll:true});
  }
}
el('triage').addEventListener('submit', async event => {
  event.preventDefault();
  if (saving) return;
  if (!selected) {el('message').textContent = 'Open an incident before saving a decision.'; return;}
  const id = selected, body = {status:el('status').value,note:el('note').value};
  const decisionStatus = el('decision-status');
  const fields = [...event.target.querySelectorAll('button, select, textarea')];
  const focused = document.activeElement;
  const previous = fields.map(field => field.disabled);
  fields.forEach(field => field.disabled = true);
  saving = true; ++detailRequest;
  let committed = false;
  decisionStatus.textContent = 'Saving decision…';
  try {
    await api('incidents/' + encodeURIComponent(id) + '/status', body);
    committed = true; el('note').value = '';
    await show(id, true); await load();
    decisionStatus.textContent = 'Decision saved.';
  } catch(error) {
    decisionStatus.textContent = committed
      ? 'Decision saved, but the view could not be refreshed. Refresh the inbox before making another decision. ' + error.message
      : error.message;
  } finally {
    saving = false;
    fields.forEach((field, index) => field.disabled = previous[index]);
    if (fields.includes(focused) && !focused.disabled && document.activeElement === document.body) {
      focused.focus({preventScroll:true});
    }
  }
});
for (const [id, reset] of [['refresh',true],['more',false]]) {
  el(id).addEventListener('click', async () => {
    if (listAction || (!reset && !cursor)) return;
    listAction = true;
    el(id).setAttribute('aria-disabled', 'true');
    if (!saving) el('message').textContent = '';
    try {await load(reset);}
    catch (error) {if (!saving) el('message').textContent = error.message;}
    finally {
      el(id).removeAttribute('aria-disabled');
      listAction = false;
    }
  });
}
api('session').then(async data => {
  csrf = data.csrf_token; await load();
  const incident = new URLSearchParams(location.search).get('incident');
  if (incident) await show(incident);
}).catch(error => el('message').textContent = error.message);
