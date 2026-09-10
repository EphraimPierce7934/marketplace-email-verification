from __future__ import annotations

import base64
import hashlib
import hmac
import html
import time
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class SellerAsset(BaseModel):
    listing_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    delivery_url: HttpUrl


class BuyerUpdates(BaseModel):
    order_updates: bool = True


class OrderHandoff(BaseModel):
    order_id: str = Field(min_length=1)
    state: Literal["awaiting_email_verification", "ready_for_handoff"]


class MarketplaceSignup(BaseModel):
    seller_id: str = Field(min_length=1)
    seller_email: EmailStr
    asset: SellerAsset
    buyer_updates: BuyerUpdates
    handoff: OrderHandoff


class SignupResult(BaseModel):
    seller_id: str
    verification: Literal["pending"]
    handoff_state: Literal["awaiting_email_verification"]
    message_id: str


class VerificationResult(BaseModel):
    seller_id: str
    handoff_state: Literal["ready_for_handoff"]


@dataclass(frozen=True)
class VerificationSigner:
    secret: bytes
    ttl_seconds: int = 3600

    def issue(self, seller_id: str, now: int | None = None) -> str:
        expires = (now if now is not None else int(time.time())) + self.ttl_seconds
        payload = f"{seller_id}:{expires}"
        signature = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()

    def verify(self, token: str, now: int | None = None) -> str:
        try:
            decoded = base64.urlsafe_b64decode(token.encode()).decode()
            seller_id, expires_text, signature = decoded.rsplit(":", 2)
            payload = f"{seller_id}:{expires_text}"
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError("invalid verification token") from exc
        expected = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid verification token")
        if int(expires_text) < (now if now is not None else int(time.time())):
            raise ValueError("expired verification token")
        return seller_id


class MarketplaceVerification:
    def __init__(self, email: Any, signer: VerificationSigner, public_url: str) -> None:
        self.email = email
        self.signer = signer
        self.public_url = public_url.rstrip("/")

    def start(self, signup: MarketplaceSignup) -> SignupResult:
        if signup.handoff.state != "awaiting_email_verification":
            raise ValueError("new handoff must await email verification")
        token = self.signer.issue(signup.seller_id)
        link = f"{self.public_url}/verify?token={token}"
        message_id = self.email.send(
            to=str(signup.seller_email),
            subject="Verify your marketplace seller email",
            html=(
                f"<p>Confirm the seller account for <strong>{html.escape(signup.asset.title)}</strong>.</p>"
                f'<p><a href="{html.escape(link, quote=True)}">Verify email</a></p>'
            ),
            idempotency_key=f"seller-verification:{signup.seller_id}:{signup.handoff.order_id}",
        )
        return SignupResult(
            seller_id=signup.seller_id,
            verification="pending",
            handoff_state="awaiting_email_verification",
            message_id=message_id,
        )

    def complete(self, token: str) -> VerificationResult:
        return VerificationResult(
            seller_id=self.signer.verify(token),
            handoff_state="ready_for_handoff",
        )
