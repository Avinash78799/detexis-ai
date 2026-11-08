"use strict";
const el = id => document.getElementById(id);
let csrf = '';
function node(tag, value) {const n = document.createElement(tag); n.textContent = value; return n;}
function result(id, title, review) {
  const box = el(id); box.replaceChildren(node('h3', title)); box.hidden = false;
  box.dataset.state = review ? 'review' : 'clear'; return box;
}
function wire(id, output, action) {
  el(id).addEventListener('submit', async event => {
    event.preventDefault(); const data = new FormData(event.target);
    const fields = event.target.querySelector('fieldset'); fields.disabled = true;
    // Hide the previous verdict before a new attempt so an error cannot leave a
    // stale clean result displayed for a different sample.
    el(output).hidden = true; el('message').textContent = 'Analyzing…';
    try {await action(data); el('message').textContent = 'Analysis complete. Review the evidence and limitations below.';}
    catch(error) {el('message').textContent = error.message;}
    finally {fields.disabled = false;}
  });
}
wire('request-form', 'request-result', async data => {
  const value = await window.shieldApi('analyze/request', {path:data.get('path'), query:data.get('query'), user_agent:data.get('user_agent'), status:Number(data.get('status'))}, csrf);
  const box = result('request-result', value.findings.length ? 'Suspicious pattern detected' : 'No pattern detected', value.findings.length > 0);
  box.append(node('p', 'Engine: ' + value.engine + ' · Severity: ' + value.severity));
  for (const finding of value.findings) {
    const item = document.createElement('article');
    item.append(node('strong', finding.reason), node('p', finding.rule_id + ' · ' + finding.cwe + ' · ' + finding.owasp));
    box.append(item);
  }
  box.append(node('p', 'Next step: ' + (value.findings.length ? 'Review application logs and input handling. Confirm context before taking action.' : 'Continue monitoring; this checks a limited set of patterns.')),
    node('p', value.scope), node('p', value.limitations));
});
wire('file-form', 'file-result', async data => {
  const file = data.get('file');
  if (!file || !file.size || file.size > 1048576) throw new Error('Choose a nonempty file no larger than 1 MiB.');
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = ''; for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  const value = await window.shieldApi('analyze/file', {content_base64:btoa(binary)}, csrf);
  const titles = {signature_detected:'Signature detected', no_signature_detected:'No signature detected', needs_review:'Inspection needs review'};
  const box = result('file-result', titles[value.verdict] || 'No verdict available', value.verdict !== 'no_signature_detected');
  if (value.signature) box.append(node('p', 'Signature: ' + value.signature));
  box.append(node('p', 'Engine: ' + value.engine), node('p', 'Bytes scanned: ' + value.bytes), node('p', 'SHA-256'), node('code', value.sha256), node('p', value.limitations));
});
window.shieldApi('session').then(async session => {
  csrf = session.csrf_token; el('request-form').querySelector('fieldset').disabled = false;
  el('message').textContent = '';
  const config = await window.shieldApi('analyze/capabilities');
  el('file-capability').textContent = config.file_scan === 'configured'
    ? 'Engine configured. Readiness and signature age are checked when you scan.'
    : 'File scanning needs operator setup. Request inspection is available.';
  el('file-form').querySelector('fieldset').disabled = config.file_scan !== 'configured';
}).catch(error => el('message').textContent = error.message);
