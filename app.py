from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

# Import your existing logic
from ride_agent import RideRequest, get_best_ride

app = FastAPI(title="Ride Agent Demo", version="1.0")


class RunRequest(BaseModel):
    pickup: str = Field(..., min_length=1, description="Pickup address or place name")
    dropoff: str = Field(..., min_length=1, description="Dropoff address or place name")
    vehicle_need: str = Field("cheapest", description="cheapest / XL / black / lux / 6 seats")


def format_text(pickup: str, dropoff: str, vehicle_need: str) -> str:
    req = RideRequest(pickup=pickup, dropoff=dropoff, vehicle_need=vehicle_need)
    res = get_best_ride(req, use_mock_if_needed=True)

    lines: list[str] = []
    lines.append("RIDE AGENT RESULTS")
    lines.append("=" * 18)
    lines.append(f"Pickup:  {res.request.pickup}")
    lines.append(f"Dropoff: {res.request.dropoff}")
    lines.append(f"Need:    {res.request.vehicle_need}")
    lines.append("")

    if not res.quotes:
        lines.append("No quotes available.")
        return "\n".join(lines)

    lines.append("Quotes:")
    for q in res.quotes:
        if q.price_low is None:
            note = f" ({q.notes})" if q.notes else ""
            lines.append(f"- {q.provider.upper():4} | {q.ride_type} | not available{note}")
        else:
            hi = f"{q.price_high:.2f}" if q.price_high is not None else "?"
            eta = f"{q.eta_minutes} min" if q.eta_minutes is not None else "?"
            lines.append(
                f"- {q.provider.upper():4} | {q.ride_type} | ${q.price_low:.2f}–${hi} {q.currency} | ETA {eta}"
            )

    if res.cheapest and res.cheapest.price_low is not None:
        c = res.cheapest
        lines.append("")
        lines.append(f"Cheapest (by low estimate): {c.provider.upper()} — {c.ride_type} at ${c.price_low:.2f}")

    return "\n".join(lines)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Ride Agent Demo</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; }
    .card { max-width: 900px; border: 1px solid #ddd; border-radius: 14px; padding: 18px; }
    label { display: block; font-weight: 600; margin-top: 12px; }
    input, select { width: 100%; padding: 10px 12px; margin-top: 6px; border: 1px solid #ccc; border-radius: 10px; font-size: 14px; }
    button { margin-top: 14px; padding: 10px 14px; border: 0; border-radius: 10px; font-weight: 700; cursor: pointer; }
    pre { white-space: pre-wrap; word-wrap: break-word; background: #f7f7f7; padding: 14px; border-radius: 12px; border: 1px solid #eee; }
    .small { color: #555; font-size: 13px; }
  </style>
</head>
<body>
  <div class=\"card\">
    <h1 style=\"margin:0 0 8px 0;\">Ride Agent (Recruiter Demo)</h1>
    <div class=\"small\">Enter a pickup & dropoff location. This demo always returns a result using a mock quote fallback.</div>

    <label for=\"pickup\">Pickup location</label>
    <input id=\"pickup\" placeholder=\"e.g., Chicago O'Hare Airport\" />

    <label for=\"dropoff\">Dropoff location</label>
    <input id=\"dropoff\" placeholder=\"e.g., Navy Pier, Chicago\" />

    <label for=\"need\">Vehicle need</label>
    <select id=\"need\">
      <option value=\"cheapest\" selected>cheapest</option>
      <option value=\"XL\">XL</option>
      <option value=\"black\">black</option>
      <option value=\"lux\">lux</option>
      <option value=\"6 seats\">6 seats</option>
    </select>

    <button onclick=\"run()\">Run</button>

    <h3 style=\"margin:18px 0 8px 0;\">Output</h3>
    <pre id=\"out\">Ready.</pre>

    <div class=\"small\" style=\"margin-top:12px;\">
      Tip: You can also call <code>/run-text?pickup=...&dropoff=...</code> for plain text.
    </div>
  </div>

<script>
async function run(){
  const pickup = document.getElementById('pickup').value.trim();
  const dropoff = document.getElementById('dropoff').value.trim();
  const vehicle_need = document.getElementById('need').value;

  const out = document.getElementById('out');
  if(!pickup || !dropoff){ out.textContent = 'Please enter both pickup and dropoff.'; return; }

  out.textContent = 'Running...';
  try{
    const r = await fetch('/run-text', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({pickup, dropoff, vehicle_need})
    });
    const t = await r.text();
    out.textContent = t;
  }catch(e){
    out.textContent = 'Error: ' + (e?.message ?? String(e));
  }
}
</script>
</body>
</html>"""


@app.post("/run-text", response_class=PlainTextResponse)
def run_text(payload: RunRequest) -> str:
    return format_text(payload.pickup, payload.dropoff, payload.vehicle_need)


@app.get("/run-text", response_class=PlainTextResponse)
def run_text_get(pickup: str, dropoff: str, vehicle_need: str = "cheapest") -> str:
    return format_text(pickup, dropoff, vehicle_need)
