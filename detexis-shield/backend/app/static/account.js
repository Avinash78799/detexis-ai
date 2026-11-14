"use strict";
let csrf = "";
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
  await refreshSites();
  if (data.recovery_code) node('recovery-secret').scrollIntoView({block:'start'});
  const next = new URLSearchParams(location.search).get('next');
  if (next && !data.recovery_code) {
    const target = new URL(next, location.origin);
    if (target.origin === location.origin && (['/app/inbox', '/app/analyze', '/app/detection'].includes(target.pathname) || /^\/app\/sites\/[0-9a-f-]+$/.test(target.pathname))) location.assign(target.pathname + target.search);
  }
}
async function refreshSites() {
  node('sites-status').textContent = 'Loading websites…';
  let sites;
  try {sites = await api('sites');}
  catch (error) {node('sites-status').textContent = 'Your websites could not be refreshed. ' + error.message; throw error;}
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
    const card = document.createElement('section'); card.className = 'account-card site-card';
    const title = document.createElement('h3'); title.textContent = site.domain;
    const header = document.createElement('div'); header.className = 'site-card-header'; header.append(title, link);
    const state = document.createElement('p'); state.className = 'site-state';
    state.textContent = (site.verified ? 'Domain verified for scans' : 'Domain verification needed for scans') + ' · ' + (site.last_heartbeat ? 'Heartbeat last received ' + new Date(site.last_heartbeat).toLocaleString() : 'Awaiting first sensor heartbeat');
    card.append(header, state);
    const connection = document.createElement('button'); connection.className = 'secondary'; connection.textContent = 'Check sensor connection';
    const connectionPanel = document.createElement('section'); connectionPanel.setAttribute('aria-live', 'polite');
    connection.addEventListener('click', async () => {
      connection.disabled = true;
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
      finally {connection.disabled = false;}
    });
    const manage = document.createElement('button'); manage.className = 'secondary'; manage.textContent = 'Manage sensor keys';
    const panel = document.createElement('div');
    manage.addEventListener('click', async () => {
      manage.disabled = true;
      try {
        const path = 'sites/' + encodeURIComponent(site.id) + '/keys';
        const keys = await api(path); panel.replaceChildren();
        for (const key of keys) {
          const row = document.createElement('p'); row.textContent = 'dxs_' + key.prefix + '_… · ' + (key.revoked ? 'Revoked' : 'Active');
          if (!key.revoked) {
            const revoke = document.createElement('button'); revoke.className = 'secondary'; revoke.textContent = 'Revoke';
            revoke.addEventListener('click', async () => {
              if (!confirm('Revoke this sensor key? Update any application using it with a replacement key first.')) return;
              try {await api(path + '/' + key.id + '/revoke', {}); manage.click();}
              catch (error) {node('message').textContent = error.message;}
            }); row.append(revoke);
          }
          panel.append(row);
        }
        const create = document.createElement('button'); create.textContent = 'Create replacement key';
        create.addEventListener('click', async () => {
          create.disabled = true;
          try {
            const issued = await api(path, {}); const secret = document.createElement('pre');
            secret.textContent = 'Save this key now; it is shown once:\n' + issued.api_key;
            panel.append(secret); create.remove();
          } catch (error) {node('message').textContent = error.message; create.disabled = false;}
        }); panel.append(create);
      } catch (error) {node('message').textContent = error.message;}
      finally {manage.disabled = false;}
    });
    const verify = document.createElement('button'); verify.className = 'secondary'; verify.textContent = site.verified ? 'Run security scan' : 'Verify domain & scan';
    const verificationPanel = document.createElement('div');
    verify.addEventListener('click', async () => {
      verify.disabled = true;
      try {
        const path = 'sites/' + encodeURIComponent(site.id);
        if (site.verified) {
          await api(path + '/scans', {});
          verificationPanel.textContent = 'Scan queued. Open this website’s dashboard for results.';
          return;
        }
        const challenge = await api(path + '/verification', {});
        verificationPanel.replaceChildren();
        const instructions = document.createElement('p'); instructions.textContent = 'Publish this TXT record in your DNS, or serve the value at the exact HTTPS URL. Then confirm ownership.';
        const proof = document.createElement('pre'); proof.textContent = 'TXT name: ' + challenge.record + '\nValue: ' + challenge.value + '\nAlternative HTTPS file: ' + challenge.http_url;
        const confirmOwnership = document.createElement('button'); confirmOwnership.textContent = 'Confirm ownership';
        confirmOwnership.addEventListener('click', async () => {
          confirmOwnership.disabled = true;
          try {
            await api(path + '/verify', {}); instructions.textContent = 'Ownership verified. You can now request a security scan.';
            const scan = document.createElement('button'); scan.textContent = 'Run security scan';
            scan.addEventListener('click', async () => {scan.disabled = true; try {await api(path + '/scans', {}); instructions.textContent = 'Scan queued. Open this website’s dashboard for results.';} catch (error) {node('message').textContent = error.message; scan.disabled = false;}});
            verificationPanel.replaceChildren(instructions, scan);
          } catch (error) {node('message').textContent = error.message; confirmOwnership.disabled = false;}
        });
        verificationPanel.append(instructions, proof, confirmOwnership);
      } catch (error) {node('message').textContent = error.message;}
      finally {verify.disabled = false;}
    });
    card.append(connection, manage, verify, connectionPanel, panel, verificationPanel); node('sites').append(card);
  }
}
for (const id of ['auth-form','site-form','recover-form','recovery-form','password-form']) node(id).addEventListener('submit', async event => {
  event.preventDefault(); node('message').textContent = '';
  const buttons = [...event.target.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true);
  try {
    const body = Object.fromEntries(new FormData(event.target));
    if (id === 'auth-form') {
      await showWorkspace(await api(event.submitter?.value || 'login', body)); event.target.reset();
    } else if (id === 'recover-form') {
      await showWorkspace(await api('recover', body)); event.target.reset();
    } else if (id === 'password-form') {
      await showWorkspace(await api('password', body)); event.target.reset();
      node('message').textContent = 'Password changed. Other sessions were signed out. Save your replacement recovery code.';
    } else if (id === 'recovery-form') {
      const issued = await api('recovery-code', body);
      node('recovery-secret').hidden = false; node('recovery-value').textContent = issued.recovery_code;
      event.target.reset(); node('recovery-secret').scrollIntoView({block:'start'});
    } else {
      const data = await api('sites', body);
      node('installation').hidden = false;
      node('credentials').textContent = 'SHIELD_URL=' + location.origin + '\nSHIELD_API_KEY=' + data.api_key + '\nSHIELD_SALT=' + data.site_salt;
      node('snippet').textContent = 'import os\nfrom detexis_shield import ShieldMiddleware\n\napp.add_middleware(ShieldMiddleware,\n    api_url=os.environ["SHIELD_URL"],\n    api_key=os.environ["SHIELD_API_KEY"],\n    site_salt=os.environ["SHIELD_SALT"],\n)';
      event.target.reset(); await refreshSites();
      node('installation').scrollIntoView({block:'start'});
    }
  } catch (error) {node('message').textContent = error.message;}
  finally {buttons.forEach(b => b.disabled = false);}
});
node('logout').addEventListener('click', async () => {try {await api('logout', {}); location.reload();} catch (error) {node('message').textContent = error.message;}});
if (location.protocol !== 'https:') {
  node('message').textContent = 'Account actions require HTTPS. Open your Shield service’s HTTPS address to sign in, create an account or recover access. The installation and data-handling guides remain available here.';
  node('auth').querySelectorAll('input, button[type="submit"]').forEach(field => field.disabled = true);
} else {
  api('session').then(showWorkspace).catch(error => {node('auth').hidden = false; if (error.status !== 401) node('message').textContent = error.message;});
}
