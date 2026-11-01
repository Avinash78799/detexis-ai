"use strict";
let csrf = "";
const node = id => document.getElementById(id);
async function api(path, body) {
  const response = await fetch('/app/api/' + path, {method: body === undefined ? 'GET' : 'POST', credentials:'same-origin', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body:body === undefined ? undefined : JSON.stringify(body)});
  const data = response.status === 204 ? {} : await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check your details and try again.');
  return data;
}
async function showWorkspace(data) {
  csrf = data.csrf_token;
  node('auth').hidden = true; node('workspace').hidden = false;
  node('owner-email').textContent = data.email;
  await refreshSites();
}
async function refreshSites() {
  const sites = await api('sites');
  node('sites').replaceChildren();
  if (!sites.length) node('sites').textContent = 'No websites yet. Add your first website above.';
  for (const site of sites) {
    const link = document.createElement('a'); link.className = 'site-link';
    link.href = '/app/sites/' + encodeURIComponent(site.id); link.textContent = site.domain + ' → Open dashboard';
    const card = document.createElement('section'); card.className = 'account-card'; card.append(link);
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
    card.append(manage, verify, panel, verificationPanel); node('sites').append(card);
  }
}
for (const id of ['auth-form','site-form']) node(id).addEventListener('submit', async event => {
  event.preventDefault(); node('message').textContent = '';
  const buttons = [...event.target.querySelectorAll('button')]; buttons.forEach(b => b.disabled = true);
  try {
    const body = Object.fromEntries(new FormData(event.target));
    if (id === 'auth-form') {
      await showWorkspace(await api(event.submitter?.value || 'login', body)); event.target.reset();
    } else {
      const data = await api('sites', body);
      node('installation').hidden = false;
      node('credentials').textContent = 'SHIELD_URL=' + location.origin + '\nSHIELD_API_KEY=' + data.api_key + '\nSHIELD_SALT=' + data.site_salt;
      node('snippet').textContent = 'import os\nfrom detexis_shield import ShieldMiddleware\n\napp.add_middleware(ShieldMiddleware,\n    api_url=os.environ["SHIELD_URL"],\n    api_key=os.environ["SHIELD_API_KEY"],\n    site_salt=os.environ["SHIELD_SALT"],\n)';
      event.target.reset(); await refreshSites();
    }
  } catch (error) {node('message').textContent = error.message;}
  finally {buttons.forEach(b => b.disabled = false);}
});
node('logout').addEventListener('click', async () => {try {await api('logout', {}); location.reload();} catch (error) {node('message').textContent = error.message;}});
api('session').then(showWorkspace).catch(() => {node('auth').hidden = false;});
