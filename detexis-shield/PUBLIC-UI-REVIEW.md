# Public onboarding browser review

On 7 November 2026, the rebuilt local API was inspected in the in-app browser.
The public workspace, installation guide and data-handling page were opened
through their rendered links. A 390 x 844 viewport was used for mobile review
and reset afterward. Document width did not exceed viewport width. Long install
commands scrolled within their code block. Recovery instructions expanded and
exposed labeled email, saved-code and new-password fields; no credentials were
entered and no account/recovery action was submitted.

The HTTP workspace initially exposed forms even though account actions require
HTTPS. It now explains that requirement, disables credential entry and submit
buttons on HTTP, and leaves public guides usable. After rebuilding/reloading,
the browser showed the warning and all credential controls disabled. A Node
regression verifies that HTTP initialization makes no session request. Seven
JavaScript tests passed across request handling, dashboard refresh and this guard.
The backend's HTTPS-origin, CSRF and secure-session checks remain in place.

This is a public-page/mobile checkpoint, not a full accessibility certification
or signed-in browser acceptance. HTTPS sign-in, account recovery submission,
signed-in error states, keyboard-only navigation and broader assistive-technology
review remain outstanding. API and headless regression evidence is recorded
separately; it must not be substituted for those browser checks.

Screenshots are retained privately in the workspace outputs folder:
`public-workspace-mobile-review.jpg` and `http-workspace-guidance-mobile.jpg`.
No private account data appears in them. The current HTTP preview is a local
development view, not the eventual public service address.
