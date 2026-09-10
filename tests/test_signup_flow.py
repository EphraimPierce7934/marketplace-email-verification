from marketplace_verification.signup_flow import MarketplaceSignup, MarketplaceVerification, VerificationSigner


class RecordingEmail:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def send(self, *, to: str, subject: str, html: str, idempotency_key: str) -> str:
        self.calls.append({"to": to, "subject": subject, "html": html, "idempotency_key": idempotency_key})
        return "msg-101"


def test_handoff_becomes_ready_only_after_signed_email_link() -> None:
    email = RecordingEmail()
    signer = VerificationSigner(b"test-secret", ttl_seconds=600)
    workflow = MarketplaceVerification(email, signer, "https://market.example")
    signup = MarketplaceSignup.model_validate(
        {
            "seller_id": "seller-42",
            "seller_email": "seller@example.com",
            "asset": {"listing_id": "asset-9", "title": "Receipt template", "delivery_url": "https://market.example/a/9"},
            "buyer_updates": {"order_updates": True},
            "handoff": {"order_id": "order-7", "state": "awaiting_email_verification"},
        }
    )

    pending = workflow.start(signup)
    assert pending.handoff_state == "awaiting_email_verification"
    assert email.calls[0]["idempotency_key"] == "seller-verification:seller-42:order-7"
    token = signer.issue("seller-42")
    completed = workflow.complete(token)
    assert completed.seller_id == "seller-42"
    assert completed.handoff_state == "ready_for_handoff"
