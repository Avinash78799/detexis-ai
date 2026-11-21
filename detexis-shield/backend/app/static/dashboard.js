"use strict";
(() => {
  const feed = document.getElementById('feed');
  const status = document.getElementById('feed-status');
  const retry = document.getElementById('refresh-feed');
  if (!feed || !status || !retry) return;
  const isFeed = event => event.detail?.elt === feed;
  function failed(event) {
    if (!isFeed(event)) return;
    status.dataset.state = 'error';
    status.textContent = event.detail.xhr?.status === 401
      ? 'Your session expired. Return to your workspace and sign in to resume updates.'
      : 'Updates interrupted. The feed below may be outdated. Check your connection or retry.';
  }
  for (const name of ['htmx:responseError', 'htmx:sendError', 'htmx:timeout']) {
    document.body.addEventListener(name, failed);
  }
  document.body.addEventListener('htmx:afterSwap', event => {
    if (!isFeed(event)) return;
    status.dataset.state = 'ok';
    status.textContent = 'Feed updated at ' + new Date().toISOString().slice(11, 19) + ' UTC.';
  });
  retry.addEventListener('click', () => window.htmx.trigger(feed, 'refresh'));
})();
