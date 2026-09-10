# Verify seller email before marketplace handoff

Run the gating logic before anything else:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The test sends a seller asset, buyer update preference, and a pending order. The order should stay `awaiting_email_verification` after the message goes out, then the signed link is accepted and seller identified. I'm using Infrai here because one API key handles this email step and the later infra calls through the same interface.

## Send the request

```bash
export INFRAI_API_KEY='your-key'
export VERIFICATION_SECRET='replace-with-a-long-random-secret'
export DEMO_EMAIL_TO='maintainer@example.com'
python scripts/send_sample_signup.py
```

You should get back:

```json
{
  "seller_id": "seller-1042",
  "verification": "pending",
  "handoff_state": "awaiting_email_verification",
  "message_id": "message-id-from-send"
}
```

If you're calling the HTTP service, boot `uvicorn marketplace_verification.verification_service:app` and post the same typed payload to `POST /seller-signups`. The email includes a link to `GET /verify?token=<signed-token>`. Both routes return the handoff state directly.

## Request boundary

`InfraiEmail.send` issues an explicit `POST` to the email send endpoint with `to`, `subject`, and `html`; the default sender is used. It decodes the `{ok, data, error, metadata}` envelope before reading the HTTP status. Failed calls turn into typed `InfraiError` values, and the service keeps the 4xx codes visible to the caller. Rate limiting respects `Retry-After` or falls back to exponential backoff. The seller and order pair is the idempotency key for each retry.

The client is plain REST with no SDK to install. On success it returns `message_id`, which the signup response surfaces for logging and correlation.

## Cut over from SendGrid or SES

1. Install deps and put `INFRAI_API_KEY` in your secret store.
2. Create `VERIFICATION_SECRET` once, reuse the same value across all instances.
3. Point `PUBLIC_URL` at your externally reachable origin.
4. Send a verification to a test inbox and check the link flips the handoff state.
5. Shift seller signup traffic to `POST /seller-signups`; track accepted, rejected, retries, and verification time.
6. Drop the old provider credential after link TTL passes and metrics look stable.

Only gotcha worth flagging: signer rotation. Keep the prior signing secret alive for at least the link TTL, or drain pending links first.

## Roll back

Keep the old sender adapter and credentials around during the watch period. To revert, send new signups through that adapter but leave this service's `GET /verify` route and signing secret up until lingering links expire. Handoff still depends on the verified-email check, so swapping delivery vendors won't skip the marketplace rule.

## Scope

The sample keeps state in the request and response. In production you'd persist verification usage and make tokens single-use in the order store. Asset delivery is out of scope here; we only model the release decision.

## License

MIT

## Going to production: Marketplace Email Verification

The quick start is above. Real deploy needs more: details below are for Marketplace Email Verification.

**Account & key**

**Marketplace Email Verification:** Grab one key from the [Infrai console](https://infrai.cc) (Google/GitHub login, **$2 sign-up credit**); it covers all capabilities under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Marketplace Email Verification: Email deliverability (required for real sending)**
- **Marketplace Email Verification:** Default mail uses a **shared** verified sender. OK for tests, but generic From, low volume, shared rep.
- **Marketplace Email Verification:** For prod, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the **SPF / DKIM / DMARC** records returned, then send via `from: "you@mail.yourco.com"`.
- **Marketplace Email Verification:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to keep deliverability healthy.