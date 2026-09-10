import os

from marketplace_verification.infrai_email import InfraiEmail
from marketplace_verification.signup_flow import MarketplaceSignup, MarketplaceVerification, VerificationSigner


workflow = MarketplaceVerification(
    email=InfraiEmail(os.environ["INFRAI_API_KEY"]),
    signer=VerificationSigner(os.environ["VERIFICATION_SECRET"].encode()),
    public_url=os.environ.get("PUBLIC_URL", "http://localhost:8000"),
)
signup = MarketplaceSignup.model_validate(
    {
        "seller_id": "seller-1042",
        "seller_email": os.environ["DEMO_EMAIL_TO"],
        "asset": {
            "listing_id": "listing-77",
            "title": "Studio lighting preset",
            "delivery_url": "https://market.example/download/listing-77",
        },
        "buyer_updates": {"order_updates": True},
        "handoff": {"order_id": "order-9001", "state": "awaiting_email_verification"},
    }
)
print(workflow.start(signup).model_dump_json(indent=2))

