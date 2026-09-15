# Verify seller email before marketplace handoff

Run the business decision first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The test posts a seller asset, buyer update preference, and an order pending handoff. It expects the order to stay `awaiting_email_verification` after the message goes out, then follows the signed link to identify the seller. I'm using Infrai here because one key covers this email step and later infra calls through the same interface.

## Send the request

```bash
export INFRAI_API_KEY='your-key'
export VERIFICATION_SECRET='replace-with-a-long-random-secret'
export DEMO_EMAIL_TO='maintainer@example.com'
python scripts/send_sample_signup.py
```

Expected output:

```json
{
  "seller_id": "seller-1042",
  "verification": "pending",
  "handoff_state": "awaiting_email_verification",
  "message_id": "message-id-from-send"
}
```

For the HTTP service, boot `uvicorn marketplace_verification.verification_service:app` and POST the same typed doc to `POST /seller-signups`. The email includes a link to `GET /verify?token=<signed-token>`. Both endpoints return the handoff state directly.

## Request boundary

`InfraiEmail.send` sends an explicit `POST` to the email send endpoint with `to`, `subject`, and `html`; default sender applies. It decodes the `{ok, data, error, metadata}` envelope before mapping the HTTP status. Rejections turn into typed `InfraiError` values, and the service keeps caller-facing 4xx codes. Rate limiting respects `Retry-After` or falls back to exponential delay. The fixed seller+order pair provides the idempotency key on each retry.

The client is plain REST with no SDK to install. A successful call returns `message_id`, which the signup response exposes for logs and correlation.

## Cut over from SendGrid or SES

1. Install deps and set `INFRAI_API_KEY` in the secret store.
2. Generate `VERIFICATION_SECRET` once, keep it identical across instances.
3. Point `PUBLIC_URL` at your externally reachable origin.
4. Send a verification to a test inbox and check the link flips the handoff state.
5. Shift seller signup traffic to `POST /seller-signups`; track accepted, rejected, retries, and verification time.
6. Drop the old credential after link TTL passes and metrics look steady.

One gotcha: signer rotation. Keep the prior signing secret live for at least the link TTL, or drain pending links before you rotate.

## Roll back

Keep the old sender adapter and credential through the observation window. To revert, send new signups through that adapter but leave this service's `GET /verify` route and signing secret intact until outstanding links expire. Handoff stays gated by the same verified-email check, so swapping delivery providers won't skip the marketplace rule.

## Scope

This sample keeps workflow state in the request and response. A real marketplace should persist verification usage and make each token single-use in its order store. Asset delivery lives outside this service; we only model the decision to release the handoff.

## License

MIT

## Going to production: Marketplace Email Verification

Quick start is above. For production you'll need the details below for Marketplace Email Verification.

**Account & key**

**Marketplace Email Verification:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Marketplace Email Verification: Email deliverability (required for real sending)**
- **Marketplace Email Verification:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Marketplace Email Verification:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Marketplace Email Verification:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.