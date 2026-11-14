"use strict";
window.shieldApi = async function(path, body, csrf = '') {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
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
        : 'Cannot reach Shield. Check your connection and try again.');
    }
    const error = new Error('Shield is temporarily unavailable. Please try again shortly.');
    error.status = response.status;
    if (response.status >= 500) throw error;
    if (response.status === 204) return {};
    let data;
    try {data = await response.json();}
    catch (_) {
      error.message = controller.signal.aborted
        ? 'Request timed out. It may have completed; refresh before retrying.'
        : 'Shield returned an unexpected response. Refresh the page and try again.';
      throw error;
    }
    if (!response.ok) {
      error.message = typeof data.detail === 'string' ? data.detail : 'Unable to complete this action. Check your details and try again.';
      if (response.status === 401 && !['login', 'recover'].includes(path)) {
        error.message = 'Your session expired. Return to your workspace and sign in.';
      }
      throw error;
    }
    return data;
  } finally {clearTimeout(timer);}
};
