import os

from fastapi import FastAPI, HTTPException, Query

from .infrai_email import InfraiEmail, InfraiError
from .signup_flow import (
    MarketplaceSignup,
    MarketplaceVerification,
    SignupResult,
    VerificationResult,
    VerificationSigner,
)


def build_workflow() -> MarketplaceVerification:
    return MarketplaceVerification(
        email=InfraiEmail(os.environ["INFRAI_API_KEY"]),
        signer=VerificationSigner(os.environ["VERIFICATION_SECRET"].encode()),
        public_url=os.environ.get("PUBLIC_URL", "http://localhost:8000"),
    )


app = FastAPI(title="Marketplace verification service")


@app.post("/seller-signups", response_model=SignupResult, status_code=202)
def create_seller_signup(signup: MarketplaceSignup) -> SignupResult:
    try:
        return build_workflow().start(signup)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail={"code": exc.code}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/verify", response_model=VerificationResult)
def verify_seller_email(token: str = Query(min_length=1)) -> VerificationResult:
    try:
        return build_workflow().complete(token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

