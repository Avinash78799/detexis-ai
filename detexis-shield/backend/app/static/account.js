"use strict";
let csrf = "";
let sitesRequest = 0;
let attentionRequest = 0;
const removedSites = new Set();
const node = id => document.getElementById(id);
async function api(path, body) {
  return window.shieldApi(path, body, csrf);
}
async function showWorkspace(data) {
  csrf = data.csrf_token;
  document.querySelector('.account-shell').classList.add('signed-in');
  document.querySelector('.account-shell > h1').textContent = 'Your security workspace.';
  document.querySelector('.account-shell > .subtitle').textContent = 'Connect your websites, check your sensors and review the signals that need attention.';
  node('auth').hidden = true; node('workspace').hidden = false;
  node('owner-email').textContent = data.email;
  node('recovery-secret').hidden = !data.recovery_code;
  node('recovery-value').textContent = data.recovery_code || '';
  refreshAttention();
  await refreshSites();
  if (data.recovery_code) node('recovery-secret').scrollIntoView({block:'start'});
  const next = new URLSearchParams(location.search).get('next');
  if (next && !data.recovery_code) {
    const target = new URL(next, location.origin);
    if (target.origin === location.origin && (['/app/inbox', '/app/analyze', '/app/detection', '/app/sensor-health'].includes(target.pathname) || /^\/app\/sites\/[0-9a-f-]+$/.test(target.pathname))) location.assign(target.pathname + target.search);
  }
}
async function refreshAttention() {
  const request = ++attentionRequest;
  const list = node('attention-items');
  const status = node('attention-status');
  const button = node('refresh-attention');
  list.replaceChildren();
  status.textContent = 'Checking for open alerts…';
  button.disabled = true;
  try {
    const signals = await api('attention');
    if (request !== attentionRequest) return;
    function add(label, href) {
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.textContent = label;
      link.href = href;
      item.append(link);
      list.append(item);
    }
    for (const incident of signals.incidents) {
      const severity = incident.severity === 'critical' ? 'Critical' : 'High';
      add(severity + ' incident on ' + incident.domain, '/app/inbox?incident=' + encodeURIComponent(incident.id));
    }
    for (const gap of signals.gaps) {
      add('Heartbeat overdue on ' + gap.domain, '/app/sensor-health#gap-' + encodeURIComponent(gap.id));
    }
    if (signals.more_incidents) add('View the full incident inbox', '/app/inbox');
    if (signals.more_gaps) add('View all sensor signals', '/app/sensor-health');
    status.textContent = list.children.length
      ? 'Open high-priority incidents and heartbeat gaps.'
      : 'No open high-priority incidents or heartbeat gaps.';
  } catch (error) {
    if (request === attentionRequest) status.textContent = 'Open alerts could not be checked. Use Refresh alerts to try again.';
  } finally {
    if (request === attentionRequest) button.disabled = false;
  }
}
function siteRemoval(site, card) {
  const box = document.createElement('details');
  box.className = 'site-removal';
  const summary = document.createElement('summary');
  summary.textContent = 'Remove website';
  summary.setAttribute('aria-label', 'Remove website ' + site.domain);
  const explanation = document.createElement('p');
  explanation.textContent = 'Remove the sensor from your application first. This deletes the website’s keys and live monitoring history. Your account and other websites stay in place. Backup copies expire under the operator’s retention policy.';
  const form = document.createElement('form');
  function field(name, label, type) {
    const wrapper = document.createElement('label');
    wrapper.textContent = label;
    const input = document.createElement('input');
    input.name = name;
    input.type = type;
    input.required = true;
    input.autocomplete = type === 'password' ? 'current-password' : 'off';
    input.maxLength = type === 'password' ? 128 : 253;
    if (type === 'password') input.minLength = 12;
    wrapper.append(input);
    return wrapper;
  }
  const submit = document.createElement('button');
  submit.className = 'danger';
  submit.type = 'submit';
  submit.textContent = 'Permanently remove website';
  const status = document.createElement('p');
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');
  form.append(field('password', 'Current password', 'password'),
              field('confirmation', 'Type ' + site.domain + ' to confirm', 'text'), submit, status);
  box.append(summary, explanation, form);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submit.disabled) return;
    const requestCsrf = csrf;
    const body = Object.fromEntries(new FormData(form));
    submit.disabled = true;
    status.textContent = 'Removing website and monitoring history…';
    try {
      await api('sites/' + encodeURIComponent(site.id) + '/delete', body);
      if (csrf !== requestCsrf) return;
      removedSites.add(site.id);
      for (const [panel, list] of [['issued-keys', 'issued-keys-list'], ['installation', 'installation-list']]) {
        const container = node(list);
        for (const item of [...container.children]) {
          if (item.getAttribute('data-site-id') === site.id) item.remove();
        }
        node(panel).hidden = !container.children.length;
      }
      node('issued-keys-status').textContent = '';
      card.remove();
      node('message').textContent = site.domain + ' and its monitoring history were removed.';
      const heading = node('sites-heading');
      heading.tabIndex = -1;
      heading.focus();
      refreshAttention();
      await refreshSites();
    } catch (error) {
      if (csrf === requestCsrf) status.textContent = error.message;
    } finally {
      form.reset();
      submit.disabled = false;
    }
  });
  return box;
}

async function refreshSites() {
  const request = ++sitesRequest;
  node('sites-status').textContent = 'Loading websites…';
  let sites;
  try {sites = await api('sites');}
  catch (error) {
    if (request !== sitesRequest) return;
    node('sites-status').textContent = 'Your websites could not be refreshed. Any websites shown below may be out of date. ' + error.message + ' Use Refresh websites to try again.';
    return;
  }
  if (request !== sitesRequest) return;
  node('sites-status').textContent = sites.length ? sites.length + (sites.length === 1 ? ' website in your workspace' : ' websites in your workspace') : '';
  node('sites').replaceChildren();
  if (!sites.length) {
    const empty = document.createElement('div'); empty.className = 'site-empty';
    const title = document.createElement('h3'); title.textContent = 'Start with one website.';
    const description = document.createElement('p'); description.textContent = 'Add its hostname above to get your private sensor credentials. Requests will appear after you install the middleware.';
    empty.append(title, description); node('sites').append(empty);
  }
  for (const site of sites) {
    const link = document.createElement('a'); link.className = 'site-link';
    link.href = '/app/sites/' + encodeURIComponent(site.id); link.textContent = 'Open dashboard →';
    link.setAttribute('aria-label', 'Open dashboard for ' + site.domain);
    const card = document.createElement('section'); card.className = 'account-card site-card';
    const title = document.createElement('h3'); title.textContent = site.domain;
    const header = document.createElement('div'); header.className = 'site-card-header'; header.append(title, link);
    const state = document.createElement('p'); state.className = 'site-state';
    state.textContent = (site.verified ? 'Domain verified for scans' : 'Domain verification needed for scans') + ' · ' + (site.last_heartbeat ? 'Heartbeat last received ' + new Date(site.last_heartbeat).toLocaleString() : 'Awaiting first sensor heartbeat');
    card.append(header, state);
    const connection = document.createElement('button'); connection.className = 'secondary'; connection.textContent = 'Check sensor connection';
    const connectionPanel = document.createElement('section'); connectionPanel.setAttribute('aria-live', 'polite');
    connection.setAttribute('aria-label', 'Check sensor connection for ' + site.domain);
    connectionPanel.id = 'connection-' + site.id;
    connectionPanel.hidden = true;
    connectionPanel.setAttribute('role', 'region');
    connectionPanel.setAttribute('aria-label', 'Sensor connection for ' + site.domain);
    connection.setAttribute('aria-controls', connectionPanel.id);
    connection.setAttribute('aria-expanded', 'false');
    connection.addEventListener('click', async () => {
      connection.disabled = true;
      connection.setAttribute('aria-expanded', 'true');
      connectionPanel.hidden = false;
      connectionPanel.setAttribute('aria-busy', 'true');
      connectionPanel.textContent = 'Checking sensor connection…';
      try {
        const status = await api('sites/' + encodeURIComponent(site.id) + '/connection');
        connectionPanel.replaceChildren();
        const title = document.createElement('h3'); title.textContent = 'Sensor connection check';
        const steps = document.createElement('ol'); steps.className = 'connection-checks';
        const heartbeat = {
          waiting: 'No heartbeat yet. Start your application with the middleware installed and wait up to one minute.',
          reporting: 'Heartbeat received within three minutes. A sensor can reach Shield.',
          overdue: 'Heartbeat overdue. Check that your application is running and can reach the Shield URL.'
        };
        if (status.recent_event_received) {
          heartbeat.waiting = 'Request telemetry reached Shield in the past three minutes. The first heartbeat may take up to one minute.';
          heartbeat.overdue = 'Request telemetry reached Shield in the past three minutes, but the heartbeat is overdue. Check the sensor sender if this continues.';
        }
        const processing = {
          waiting: 'No request events received yet. Visit a route in your instrumented application and check again after a few seconds.',
          pending: 'The latest received event is waiting for processing. Check again shortly.',
          processed: 'The latest received event has been processed. A normal request may produce no incident.',
          delayed: 'The latest received event has waited over one minute. Contact the Shield operator to check workers and the queue.'
        };
        for (const message of [status.active_key ? 'An active sensor key is available. Use the key assigned to this website.' : 'All sensor keys are revoked. Create a replacement key and update your application.', heartbeat[status.heartbeat], processing[status.latest_event_processing]]) {
          const step = document.createElement('li'); step.textContent = message; steps.append(step);
        }
        const stamp = document.createElement('p'); stamp.textContent = 'Checked ' + new Date(status.checked_at).toLocaleString() + '. Latest heartbeat: ' + (status.last_heartbeat ? new Date(status.last_heartbeat).toLocaleString() : 'none') + '. Latest event received: ' + (status.last_event_received_at ? new Date(status.last_event_received_at).toLocaleString() : 'none') + '.';
        const help = document.createElement('p'); help.textContent = 'If events are missing, confirm SHIELD_URL, SHIELD_API_KEY and your stable private SHIELD_SALT, restart the application, and allow outbound HTTPS. This SDK needs a persistent Python process; short-lived serverless functions are not supported. Quiet traffic alone does not prove the sensor is offline.';
        connectionPanel.append(title, steps, stamp, help);
      } catch (error) {connectionPanel.textContent = error.message;}
      finally {connection.disabled = false; connectionPanel.setAttribute('aria-busy', 'false');}
    });
    const manage = document.createElement('button'); manage.className = 'secondary'; manage.textContent = 'Manage sensor keys';
    const panel = document.createElement('div');
    manage.setAttribute('aria-label', 'Manage sensor keys for ' + site.domain);
    panel.id = 'keys-' + site.id;
    panel.setAttribute('role', 'region');
    panel.setAttribute('aria-label', 'Sensor keys for ' + site.domain);
    manage.setAttribute('aria-controls', panel.id);
    const keyStatus = document.createElement('p'); keyStatus.setAttribute('role', 'status'); keyStatus.setAttribute('aria-atomic', 'true');
    keyStatus.setAttribute('aria-live', 'polite');
    manage.addEventListener('click', async () => {
      manage.disabled = true;
      keyStatus.textContent = 'Loading sensor keys for ' + site.domain + '…';
      try {
        const path = 'sites/' + encodeURIComponent(site.id) + '/keys';
        const keys = await api(path); panel.replaceChildren();
        keyStatus.textContent = keys.length + (keys.length === 1 ? ' sensor key' : ' sensor keys') + ' for ' + site.domain;
        for (const key of keys) {
          const row = document.createElement('p'); row.textContent = 'dxs_' + key.prefix + '_… · ' + (key.revoked ? 'Revoked' : 'Active');
          if (!key.revoked) {
            const revoke = document.createElement('button'); revoke.className = 'secondary'; revoke.textContent = 'Revoke';
            revoke.setAttribute('aria-label', 'Revoke key dxs_' + key.prefix + '_… for ' + site.domain);
            revoke.addEventListener('click', async () => {
              if (!confirm('Revoke this sensor key? Update any application using it with a replacement key first.')) return;
              try {await api(path + '/' + key.id + '/revoke', {}); manage.click();}
              catch (error) {node('message').textContent = error.message;}
            }); row.append(revoke);
          }
          panel.append(row);
        }
        const create = document.createElement('button'); create.textContent = 'Create replacement key';
        create.setAttribute('aria-label', 'Create replacement key for ' + site.domain);
        create.addEventListener('click', async () => {
          create.disabled = true;
          const issuanceCsrf = csrf;
          try {
            const issued = await api(path, {}); const secret = document.createElement('pre');
            if (csrf !== issuanceCsrf || removedSites.has(site.id)) return;
            secret.textContent = 'Save this key now; it is shown once:\n' + issued.api_key;
            const saved = document.createElement('section');
            saved.setAttribute('data-site-id', site.id);
            const heading = document.createElement('h3'); heading.textContent = site.domain;
            saved.append(heading, secret); node('issued-keys-list').append(saved);
            node('issued-keys').hidden = false;
            node('issued-keys-status').textContent = 'Replacement key created for ' + site.domain + '. Save it before leaving this page.';
            node('issued-keys').scrollIntoView({block:'start'});
            create.remove();
            keyStatus.textContent = 'Replacement key created. Save the private key shown below; it is displayed once.';
          } catch (error) {node('message').textContent = error.message; create.disabled = false;}
        }); panel.append(create);
      } catch (error) {keyStatus.textContent = 'Sensor keys could not be loaded for ' + site.domain + '. ' + error.message;}
      finally {manage.disabled = false;}
    });
    const verify = document.createElement('button'); verify.className = 'secondary'; verify.textContent = site.verified ? 'Run security scan' : 'Verify domain & scan';
    verify.setAttribute('aria-label', verify.textContent + ' for ' + site.domain);
    const verificationPanel = document.createElement('div');
    verificationPanel.id = 'verification-' + site.id;
    verify.setAttribute('aria-controls', verificationPanel.id);
    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    verificationPanel.append(status);
    const path = 'sites/' + encodeURIComponent(site.id);
    async function scan(initiator) {
      initiator.disabled = true;
      status.textContent = 'Requesting a security scan…';
      try {
        await api(path + '/scans', {});
        status.textContent = 'Scan queued. Open this website’s dashboard for results.';
      } catch (error) {
        status.textContent = error.message;
      } finally {
        initiator.disabled = false;
      }
    }
    verify.addEventListener('click', async () => {
      if (site.verified) return scan(verify);
      if (verify.getAttribute('aria-expanded') === 'true') {
        verificationPanel.hidden = true;
        verify.setAttribute('aria-expanded', 'false');
        return;
      }
      verificationPanel.hidden = false;
      verify.setAttribute('aria-expanded', 'true');
    });
    if (!site.verified) {
      verificationPanel.hidden = true;
      verify.setAttribute('aria-expanded', 'false');
      const instructions = document.createElement('p');
      instructions.textContent = 'Already published a Shield proof? Confirm it here. Generate a new proof only if you need to replace it.';
      const proof = document.createElement('pre'); proof.hidden = true;
      const generate = document.createElement('button'); generate.textContent = 'Generate new proof';
      const confirmOwnership = document.createElement('button'); confirmOwnership.textContent = 'Confirm published proof';
      generate.setAttribute('aria-label', 'Generate new proof for ' + site.domain);
      confirmOwnership.setAttribute('aria-label', 'Confirm published proof for ' + site.domain);
      async function verifyAction(action) {
        generate.disabled = true;
        confirmOwnership.disabled = true;
        try {
          await action();
        } catch (error) {
          status.textContent = error.message;
        } finally {
          generate.disabled = false;
          confirmOwnership.disabled = false;
        }
      }
      generate.addEventListener('click', () => verifyAction(async () => {
        status.textContent = 'Generating a new ownership proof…';
        const challenge = await api(path + '/verification', {});
        proof.textContent = 'TXT name: ' + challenge.record + '\nValue: ' + challenge.value + '\nAlternative HTTPS file: ' + challenge.http_url;
        proof.hidden = false;
        status.textContent = 'Publish this TXT record in your DNS or serve the value at the exact HTTPS URL, then confirm it. A new proof replaces any previous one.';
      }));
      confirmOwnership.addEventListener('click', () => verifyAction(async () => {
        status.textContent = 'Checking the published proof…';
        await api(path + '/verify', {});
        site.verified = true;
        verify.textContent = 'Run security scan';
        verify.setAttribute('aria-label', 'Run security scan for ' + site.domain);
        verify.removeAttribute('aria-expanded');
        status.textContent = 'Ownership verified. You can now request a security scan.';
        verificationPanel.replaceChildren(status);
        verify.focus();
      }));
      verificationPanel.append(instructions, generate, confirmOwnership, proof);
    }
    card.append(connection, manage, verify, connectionPanel, keyStatus, panel, verificationPanel, siteRemoval(site, card)); node('sites').append(card);
  }
}
node('refresh-attention').addEventListener('click', refreshAttention);
node('refresh-sites').addEventListener('click', async () => {
  node('refresh-sites').disabled = true;
  try {await refreshSites();}
  finally {node('refresh-sites').disabled = false;}
});
for (const id of ['auth-form','site-form','recover-form','recovery-form','password-form']) node(id).addEventListener('submit', async event => {
  event.preventDefault(); node('message').textContent = '';
  const buttons = [...event.target.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true);
  try {
    const body = Object.fromEntries(new FormData(event.target));
    if (id === 'auth-form') {
      await showWorkspace(await api(event.submitter?.value || 'login', body)); event.target.reset();
    } else if (id === 'recover-form') {
      await showWorkspace(await api('recover', body)); event.target.reset();
      node('message').textContent = 'Account recovered. Other sessions were signed out. Save your replacement recovery code; the previous code has expired.';
    } else if (id === 'password-form') {
      await showWorkspace(await api('password', body)); event.target.reset();
      node('message').textContent = 'Password changed. Other sessions were signed out. Save your replacement recovery code.';
    } else if (id === 'recovery-form') {
      const issued = await api('recovery-code', body);
      node('recovery-secret').hidden = false; node('recovery-value').textContent = issued.recovery_code;
      event.target.reset(); node('recovery-secret').scrollIntoView({block:'start'});
      node('message').textContent = 'Recovery code replaced. Save the new code; the previous code has expired.';
    } else {
      const creationCsrf = csrf;
      const data = await api('sites', body);
      if (csrf !== creationCsrf || removedSites.has(data.id)) return;
      const saved = document.createElement('section');
      saved.setAttribute('data-site-id', data.id);
      const heading = document.createElement('h3');
      heading.textContent = data.domain;
      heading.tabIndex = -1;
      const credentials = document.createElement('pre');
      credentials.textContent = 'SHIELD_URL=' + location.origin + '\nSHIELD_API_KEY=' + data.api_key + '\nSHIELD_SALT=' + data.site_salt;
      saved.append(heading, credentials);
      node('installation-list').append(saved);
      node('installation').hidden = false;
      event.target.reset(); await refreshSites();
      if (csrf === creationCsrf) heading.focus();
    }
  } catch (error) {node('message').textContent = error.message;}
  finally {buttons.forEach(b => b.disabled = false);}
});
node('logout').addEventListener('click', async () => {try {await api('logout', {}); location.reload();} catch (error) {node('message').textContent = error.message;}});
node('delete-account-form').addEventListener('submit', async event => {
  event.preventDefault();
  const body = Object.fromEntries(new FormData(event.target));
  const fields = [...node('workspace').querySelectorAll('button, input')];
  const states = fields.map(field => field.disabled);
  fields.forEach(field => field.disabled = true);
  node('delete-status').textContent = 'Removing your account and monitoring history…';
  try {
    await api('account/delete', body);
    ++sitesRequest;
    ++attentionRequest;
    removedSites.clear();
    node('attention-items').replaceChildren();
    node('attention-status').textContent = '';
    csrf = '';
    node('workspace').hidden = true; node('auth').hidden = false;
    for (const id of ['recovery-value', 'owner-email']) node(id).textContent = '';
    node('installation-list').replaceChildren();
    node('issued-keys-list').replaceChildren(); node('issued-keys-status').textContent = '';
    node('issued-keys').hidden = true;
    node('sites').replaceChildren();
    node('sites-status').textContent = '';
    node('recovery-secret').hidden = true; node('installation').hidden = true;
    document.querySelector('.account-shell').classList.remove('signed-in');
    document.querySelector('.account-shell > h1').textContent = 'Your account was deleted.';
    document.querySelector('.account-shell > .subtitle').textContent = 'Your sensor keys and saved workspace history were removed from the live database.';
    node('message').textContent = 'All sessions were signed out. Backup copies follow the operator’s retention policy.';
    for (const id of ['auth-form', 'site-form', 'recovery-form', 'password-form', 'recover-form']) node(id).reset();
    node('auth').querySelector('input').focus();
  } catch (error) {node('delete-status').textContent = error.message;}
  finally {
    fields.forEach((field, index) => field.disabled = states[index]);
    event.target.reset();
  }
});
if (location.protocol !== 'https:') {
  node('message').textContent = 'Account actions require HTTPS. Open your Shield service’s HTTPS address to sign in, create an account or recover access. The installation and data-handling guides remain available here.';
  node('auth').querySelectorAll('input, button[type="submit"]').forEach(field => field.disabled = true);
} else {
  api('session').then(showWorkspace).catch(error => {node('auth').hidden = false; if (error.status !== 401) node('message').textContent = error.message;});
}
