"use strict";
(() => {
  const feed = document.getElementById('feed');
  const status = document.getElementById('feed-status');
  const updated = document.getElementById('feed-updated');
  const retry = document.getElementById('refresh-feed');
  const pause = document.getElementById('pause-feed');
  if (!feed || !status || !updated || !retry || !pause) return;
  let paused = false;
  let manual = false;
  const manualRequests = new WeakSet();
  const isFeed = event => event.detail?.elt === feed;
  const reading = () => feed.contains(document.activeElement) || feed.querySelector('details[open]');

  document.body.addEventListener('htmx:beforeRequest', event => {
    if (!isFeed(event)) return;
    if (reading() || (paused && !manual)) {
      event.preventDefault();
      return;
    }
    if (manual) manualRequests.add(event.detail.xhr);
  });
  document.body.addEventListener('htmx:beforeSwap', event => {
    if (event.detail?.target === feed && event.detail.shouldSwap &&
        (reading() || (paused && !manualRequests.has(event.detail.xhr)))) {
      event.preventDefault();
    }
  });

  function showStatus(message, state = 'ok') {
    if (status.dataset.state !== state) status.dataset.state = state;
    if (status.textContent !== message) status.textContent = message;
  }
  function failed(event) {
    if (!isFeed(event)) return;
    showStatus(event.detail.xhr?.status === 401
      ? 'Your session expired. Return to your workspace and sign in to resume updates.'
      : 'Updates interrupted. The feed below may be outdated. Check your connection or retry.', 'error');
  }
  for (const name of ['htmx:responseError', 'htmx:sendError', 'htmx:timeout']) {
    document.body.addEventListener(name, failed);
  }
  document.body.addEventListener('htmx:afterSwap', event => {
    if (!isFeed(event)) return;
    showStatus(paused ? 'Automatic updates paused.' : 'Automatic updates on.');
    updated.textContent = 'Last updated at ' + new Date().toISOString().slice(11, 19) + ' UTC.';
  });
  retry.addEventListener('click', () => {
    if (reading()) {
      showStatus('Close open scan details before refreshing the feed.');
      return;
    }
    manual = true;
    try { window.htmx.trigger(feed, 'refresh'); }
    finally { manual = false; }
  });
  pause.addEventListener('click', () => {
    paused = !paused;
    pause.textContent = paused ? 'Resume automatic updates' : 'Pause automatic updates';
    showStatus(paused ? 'Automatic updates paused.' : 'Automatic updates on.');
  });
  pause.hidden = false;
})();
