from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List, Optional, Literal, Dict, Any

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# ----------------------------
# Reliable .env loading
# ----------------------------
ENV_PATH = Path(__file__).with_name(".env")
load_dotenv(dotenv_path=ENV_PATH)

# Optional (only used if you later enable ChatGPT parsing)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Future provider creds (optional for now)
LYFT_CLIENT_ID = os.getenv("LYFT_CLIENT_ID", "")
LYFT_CLIENT_SECRET = os.getenv("LYFT_CLIENT_SECRET", "")
UBER_BEARER_TOKEN = os.getenv("UBER_BEARER_TOKEN", "")
UBER_SERVER_TOKEN = os.getenv("UBER_SERVER_TOKEN", "")

Provider = Literal["mock", "lyft", "uber"]

# ----------------------------
# Models
# ----------------------------
class LatLng(BaseModel):
    lat: float
    lng: float

class RideRequest(BaseModel):
    pickup: str = Field(..., description="Pickup address or place name")
    dropoff: str = Field(..., description="Dropoff address or place name")
    vehicle_need: str = Field("cheapest", description="cheapest / XL / black / lux / 6 seats")

class Quote(BaseModel):
    provider: Provider
    ride_type: str
    price_low: Optional[float] = None
    price_high: Optional[float] = None
    currency: str = "USD"
    eta_minutes: Optional[int] = None
    notes: Optional[str] = None

class QuoteResult(BaseModel):
    request: RideRequest
    quotes: List[Quote]
    cheapest: Optional[Quote] = None

# ----------------------------
# Utils
# ----------------------------
def pick_cheapest(quotes: List[Quote]) -> Optional[Quote]:
    priced = [q for q in quotes if q.price_low is not None]
    return min(priced, key=lambda q: q.price_low) if priced else None

def safe_float(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

# ----------------------------
# Geocoding (Nominatim OpenStreetMap)
# ----------------------------
def geocode_nominatim(place: str) -> LatLng:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": place, "format": "json", "limit": 1}
    headers = {"User-Agent": "ride-agent/1.0 (learning project)"}
    r = requests.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise RuntimeError(f"Could not geocode: '{place}'")
    return LatLng(lat=float(data[0]["lat"]), lng=float(data[0]["lon"]))

# ----------------------------
# Provider hooks (FINISHED STRUCTURE, real APIs later)
# For now, these return [] unless configured.
# ----------------------------
def get_lyft_quotes(_start: LatLng, _end: LatLng) -> List[Quote]:
    # Placeholder: we'll implement later once you have Lyft creds
    if not (LYFT_CLIENT_ID and LYFT_CLIENT_SECRET):
        return []
    return []  # real Lyft integration later

def get_uber_quotes(_start: LatLng, _end: LatLng) -> List[Quote]:
    # Placeholder: we'll implement later once you have Uber creds
    if not (UBER_BEARER_TOKEN or UBER_SERVER_TOKEN):
        return []
    return []  # real Uber integration later

# ----------------------------
# Always-works mock fallback
# ----------------------------
def get_mock_quotes(req: RideRequest) -> List[Quote]:
    # You can later make this smarter by varying based on distance/vehicle_need
    base = [
        Quote(provider="mock", ride_type="UberX (mock)", price_low=22.50, price_high=24.00, eta_minutes=6),
        Quote(provider="mock", ride_type="Lyft (mock)", price_low=19.75, price_high=23.00, eta_minutes=7),
    ]
    # tiny adjustment example
    if req.vehicle_need.strip().lower() in ("xl", "6 seats", "6-seats", "suv"):
        for q in base:
            q.ride_type = q.ride_type.replace("(mock)", "XL (mock)")
            if q.price_low is not None:
                q.price_low += 10
            if q.price_high is not None:
                q.price_high += 12
    return base

# ----------------------------
# Core engine (this is the “finished” part)
# ----------------------------
def get_best_ride(req: RideRequest, use_mock_if_needed: bool = True) -> QuoteResult:
    # 1) Geocode
    start = geocode_nominatim(req.pickup)
    end = geocode_nominatim(req.dropoff)

    # 2) Collect quotes from providers (empty until configured)
    quotes: List[Quote] = []
    quotes.extend(get_lyft_quotes(start, end))
    quotes.extend(get_uber_quotes(start, end))

    # 3) Fallback to mock if nothing priced is available
    if use_mock_if_needed and not any(q.price_low is not None for q in quotes):
        quotes = get_mock_quotes(req)

    # 4) Choose cheapest
    cheapest = pick_cheapest(quotes)

    return QuoteResult(request=req, quotes=quotes, cheapest=cheapest)

# ----------------------------
# CLI UX (simple + robust)
# ----------------------------
def prompt_user() -> RideRequest:
    print("\nRide Agent (finished core + mock mode, real APIs later)\n")

    pickup = input("Pickup location: ").strip()
    while not pickup:
        pickup = input("Pickup location (can't be empty): ").strip()

    dropoff = input("Dropoff location: ").strip()
    while not dropoff:
        dropoff = input("Dropoff location (can't be empty): ").strip()

    vehicle_need = input("Vehicle need (cheapest / XL / black / lux / 6 seats) [default: cheapest]: ").strip()
    if not vehicle_need:
        vehicle_need = "cheapest"

    return RideRequest(pickup=pickup, dropoff=dropoff, vehicle_need=vehicle_need)

def print_result(res: QuoteResult) -> None:
    req = res.request
    print("\n==============================")
    print("RESULTS")
    print("==============================")
    print(f"Pickup:  {req.pickup}")
    print(f"Dropoff: {req.dropoff}")
    print(f"Need:    {req.vehicle_need}\n")

    if not res.quotes:
        print("No quotes available.")
        return

    for q in res.quotes:
        if q.price_low is None:
            print(f"- {q.provider.upper():4} | {q.ride_type:20} | not available {f'({q.notes})' if q.notes else ''}")
        else:
            hi = f"{q.price_high:.2f}" if q.price_high is not None else "?"
            eta = f"{q.eta_minutes} min" if q.eta_minutes is not None else "?"
            print(f"- {q.provider.upper():4} | {q.ride_type:20} | ${q.price_low:.2f}–${hi} {q.currency} | ETA {eta}")

    if res.cheapest:
        c = res.cheapest
        print(f"\n✅ Cheapest (by low estimate): {c.provider.upper()} — {c.ride_type} at ${c.price_low:.2f}")
    else:
        print("\n⚠️ Could not determine cheapest (no priced quotes).")

def main() -> None:
    try:
        req = prompt_user()
        res = get_best_ride(req, use_mock_if_needed=True)
        print_result(res)
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    main()

