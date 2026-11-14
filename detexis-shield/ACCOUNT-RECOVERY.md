# Account recovery without an email sender

Shield supports a private offline recovery code so users can recover an account
without paid email infrastructure. Email addresses currently serve as sign-in
identifiers; this does not prove mailbox ownership. Email verification and
email-based resets require a configured sender and remain separate work.

## User flow

1. After registration, save the recovery code displayed in your workspace in a
   password manager or another private location. It can replace your password.
2. If you forget the password, expand **Recover your account** on the sign-in
   page. Enter your account email, saved code and a new password.
3. Successful recovery signs out all old browser sessions, signs in the current
   browser and displays a replacement recovery code. Save that replacement.
   The previous code no longer works.
4. If you still know your password but lost the code, use **Account recovery
   settings** in your workspace. Creating a replacement requires the current
   password and invalidates the old recovery code.
5. **Change password** also signs out other browser sessions and replaces the
   recovery code. Sensor API keys are separate credentials; manage them using
   the website's key controls.

If both your password and recovery code are lost, an email address alone cannot
reset the account with this configuration. There is no public administrator
bypass endpoint. Store the code before relying on this recovery method.

## Implementation and checks

- Codes contain 32 bytes of cryptographic randomness and are shown once.
  The database stores a purpose-prefixed SHA-256 verifier, never the raw code.
- Passwords use Argon2id. Browser session tokens are independently random and
  hashed in storage. All account responses are marked `no-store`.
- Recovery requests require a matching HTTPS Origin and share login rate limits.
  Authenticated code/password changes additionally require a CSRF token and
  current-password confirmation, with a separate per-user rate limit.
- PostgreSQL row locking serializes recovery and password authentication so a
  consumed code cannot reset twice and an old-password login cannot issue a new
  session after the reset has committed.
- Local tests cover single use, code rotation, old-session revocation, old-password
  rejection, current-password checks, CSRF and malformed origins. The real-service
  CI test includes two simultaneous recovery attempts and expects exactly one
  success. CI results must be checked before claiming that concurrency gate passed.

Recovery codes must not appear in URLs, logs, screenshots, committed files or
support messages. The UI does not store browser session tokens in local storage.
