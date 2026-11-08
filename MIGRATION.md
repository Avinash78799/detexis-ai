# Detexis AI → Detexis Shield

This is an intentional product migration on the Shield branch, not a compatibility
claim for the original nine-feature predictor. That flow model cannot classify
SDK URL telemetry or identify malware. Its fixed metrics, mock IP addresses and
startup training are not carried into the active product.

## Before deploying the root entry point

1. Keep a private backup of any legacy database and its operator configuration.
   Existing legacy accounts and history are not imported into Shield. Do not
   expose the old unscoped alerts/whitelist tables through the new service.
2. Start and validate the separate Shield computer instance. Create a Shield
   account over its HTTPS origin; save its recovery code privately.
3. Set `SHIELD_PUBLIC_ORIGIN=https://YOUR-CURRENT-SHIELD-HOST` in the existing
   Vercel deployment's environment settings. This value is public configuration,
   not a password. Do not put account credentials or sensor keys in it.
4. Preview this branch. Verify `/`, `/health`, `/shield` and `/analyze`; verify
   sign-in at the separate Shield origin. Try an old `/predict` POST: it must
   return a migration explanation with status 410 and must not forward its body.
5. Deploy only after the preview and backend checks pass. This repository change
   alone does not mean the existing Vercel production URL has been updated.

The root environment uses Python 3.12 (`.python-version`), Flask 3.1.3 and no ML or database dependencies. The obsolete patch-pinned `runtime.txt` is archived. Gunicorn
is pinned for Linux hosts; Vercel supplies its own Python adapter. Ownership
proof remains opt-in via `SHIELD_VERIFICATION_TOKEN` and the fixed well-known path.
Verify ownership through Shield before requesting a domain scan.

## Changed routes and accounts

- `/shield` sends a GET navigation to the configured origin's `/app`.
- `/analyze` opens its authenticated `/app/analyze` tools.
- Old predictor, upload, account, correlation and whitelist endpoints return 410.
  They do not accept or transfer credentials, files or changes to legacy data.
- A legacy account is not a Shield account. Sessions, recovery codes and keys
  belong to the Shield origin. No shared-cookie or password-copy mechanism exists.
- A link does not attach a persistent background SDK to Vercel. Ownership-verified
  scanning and on-demand analysis work separately. Continuous request telemetry
  requires a supported persistent Python application with the sensor installed.

A temporary tunnel's hostname changes after restart. Update the public-origin
setting and redeploy the entry point when that happens. The landing page does not
probe backend availability, and its `/health` is entry-point liveness only.

## Preservation and rollback

`archive/detexis-ai-app.py.txt` and `archive/detexis-ai-requirements.txt` preserve
the previous source/dependencies without executing them at startup. The original
models, templates and CSV assets remain in the repository. No migration script
modifies the old database. They are historical artifacts, not supported runtimes.

Vercel can roll back to the prior deployment if entry-point navigation fails.
That restores the old app's behavior and known limitations; it does not roll back
Shield's separate database. Keep the legacy application private if examining it.
Do not start the archived experiment on the public computer-hosted Shield origin.
