"use strict";
window.shieldApi = async function(path, body, csrf = '') {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  const removingSite = /^sites\/[^/]+\/delete$/.test(path);
  try {
    let response;
    try {
      response = await fetch('/app/api/' + path, {
        method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
        body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal,
      });
    } catch (error) {
      throw new Error(controller.signal.aborted
        ? (body === undefined ? 'Request timed out. Check your connection and retry.'
          : 'Request timed out. It may have completed; refresh before retrying.')
        : (body === undefined ? 'Cannot reach Shield. Check your connection and try again.'
          : 'Connection lost. The action may have completed; refresh before retrying.'));
    }
    const error = new Error('Shield is temporarily unavailable. Please try again shortly.');
    error.status = response.status;
    if (response.status >= 500) {
      if (body !== undefined) error.message = 'The action could not be confirmed. It may have completed; refresh before retrying.';
      if (path === 'account/delete') error.message = 'Account removal could not be confirmed. Refresh before retrying.';
      if (removingSite) error.message = 'Website removal could not be confirmed. Refresh before retrying.';
      throw error;
    }
    if (response.status === 204) return {};
    let data;
    try {data = await response.json();}
    catch (_) {
      error.message = controller.signal.aborted
        ? 'Request timed out. It may have completed; refresh before retrying.'
        : (body === undefined ? 'Shield returned an unexpected response. Refresh the page and try again.'
          : 'Shield returned an unreadable response. The action may have completed; refresh before retrying.');
      throw error;
    }
    if (!response.ok) {
      error.message = typeof data.detail === 'string' ? data.detail : 'Unable to complete this action. Check your details and try again.';
      if (response.status === 401 && !removingSite && !['login', 'recover', 'password', 'recovery-code', 'account/delete'].includes(path)) {
        error.message = 'Your session expired. Return to your workspace and sign in.';
      }
      throw error;
    }
    return data;
  } finally {clearTimeout(timer);}
};
