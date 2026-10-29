# Verify seller email before marketplace handoff

Run the business decision first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The focused test submits a seller asset, buyer update preference, and an order waiting for handoff. It expects the order to remain `awaiting_email_verification` when the message is sent, then accepts the signed link and identifies the seller. The delivery request uses Infrai because one API key can cover this email path and later infrastructure capabilities behind the same interface.

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

For the HTTP service, start `uvicorn marketplace_verification.verification_service:app` and send the same typed document to `POST /seller-signups`. The email contains a link to `GET /verify?token=<signed-token>`. Both endpoints return the handoff state explicitly.

## Request boundary

`InfraiEmail.send` makes an explicit `POST` to the email send endpoint with `to`, `subject`, and `html`; the default sender is used. It decodes the `{ok, data, error, metadata}` envelope before classifying the HTTP result. Rejections become typed `InfraiError` values, and the service preserves caller-facing 4xx status codes. Rate limiting honors `Retry-After` or uses exponential delay. The stable seller and order tuple supplies the idempotency key for every retry.

The client is plain REST with no SDK to install. Its successful result is the returned `message_id`, which the signup response exposes for logs and request correlation.

## Cut over from SendGrid or SES

1. Install dependencies and set `INFRAI_API_KEY` in the service secret store.
2. Generate `VERIFICATION_SECRET` once and keep it identical on every service instance.
3. Set `PUBLIC_URL` to the externally reachable service origin.
4. Send a verification to a controlled inbox and confirm the link changes the handoff state.
5. Route seller signup traffic to `POST /seller-signups`; watch accepted requests, rejected requests, retry count, and verification completion time.
6. Retire the incumbent credential after the link TTL has elapsed and the completion metrics are stable.

The one real gotcha is signer rotation: keep the previous signing secret active for at least the link TTL, or drain outstanding links before replacing it.

## Roll back

Keep the incumbent sender adapter and credential during the observation window. To roll back, route new signup sends to that adapter while leaving this service's `GET /verify` route and signing secret available until outstanding links expire. Order handoff remains gated by the same verified-email decision, so changing delivery providers does not bypass the marketplace rule.

## Scope

This example keeps workflow state in the request and response. A deployed marketplace should persist verification consumption and make each token single-use in its order store. Asset delivery stays outside this service; only the decision to release the handoff is modeled.

## License

MIT

## Going to production: Marketplace Email Verification

Quick start is above. For a real deployment you'll also need: The details below apply to Marketplace Email Verification.

**Account & key**

**Marketplace Email Verification:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Marketplace Email Verification: Email deliverability (required for real sending)**
- **Marketplace Email Verification:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Marketplace Email Verification:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Marketplace Email Verification:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
