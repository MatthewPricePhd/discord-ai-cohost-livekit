# Session Spend Widget — Developer Hand‑off

**Goal:** Implement a small dashboard widget that lets a user press **Start** to mark the beginning of a usage session and **Stop** to compute an **estimated cost** for the interval.

> This approach uses the **Usage API** for per‑minute/per‑hour token counts and a **model pricing map** to estimate dollars. Optionally, you can cross‑check with the **Costs API** (daily buckets only) for reconciliation.

---

## 1) What you’ll build

A UI component with two buttons and a summary line:

- **Start Session** → saves a Unix timestamp `t_start`.
- **Stop Session** → saves `t_end`, fetches usage between `t_start` and `t_end`, multiplies tokens by model prices, and displays:
  - Est. cost (USD)
  - Token totals (input / output / cached)
  - Breakdown by model (optional)

You can persist sessions in your app DB (e.g., `sessions(id, started_at, ended_at, project_id, user_id, est_cost_usd, breakdown_json)`).

---

## 2) Permissions & keys

- Use an **Admin API key** if you need org‑wide usage across projects/keys/users.
- If your app runs inside a single **Project**, a project‑scoped key plus the right `group_by` filters may be enough.
- Never expose keys to the browser—call the APIs from your backend.

---

## 3) Core API calls

### Usage (tokens)

**Endpoint:** `GET https://api.openai.com/v1/organization/usage/completions`

**Recommended params:**

- `start_time` (required) — Unix seconds
- `end_time` — Unix seconds
- `bucket_width` — `1m` (per‑minute) or `1h` (hourly) for sessions; `1d` for longer periods
- `group_by` — at minimum include `model`; you can also add `project_id`, `api_key_id`, `user_id`
- Optional filters: `project_ids`, `api_key_ids`, `user_ids`, `models`, `batch`

**Response shape (per bucket):** `results[].input_tokens`, `output_tokens`, `input_cached_tokens`, `num_model_requests`, plus group fields (`model`, etc.).

### Costs (dollars)

**Endpoint:** `GET https://api.openai.com/v1/organization/costs`

- Best for **daily** aggregation and reconciliation.
- Params: `start_time`, `bucket_width` (currently `1d`), `limit`; supports grouping (e.g., `project_id`, `line_item`).
- Not suitable for minute‑level session windows; use Usage+pricing map for session estimates.

---

## 4) Pricing map

Maintain a server‑side table mapping **model → price per 1K input/output tokens** (and, where relevant, reasoning / audio tokens). Keep this in code or a DB and update with pricing changes.

Example (illustrative only — fill with the models you actually use):

```json
{
  "gpt-4o-2024-08-06": { "input": 2.50, "output": 5.00 },
  "gpt-4o-mini-2024-07-18": { "input": 0.50, "output": 1.50 },
  "o3-mini": { "input": 1.10, "output": 4.40 }
}
```

> Units = USD per 1,000 tokens. For models with separate categories (e.g., **reasoning tokens**, **audio tokens**), include those as needed.

**Cost formula (per model):**

```
input_cost_usd  = (sum_input_tokens / 1000)  * price.input
output_cost_usd = (sum_output_tokens / 1000) * price.output
cached_input_discount? If your org has cache credits/pricing, reflect that here.
```

Total = sum over models.

---

## 5) Button flow & session logic

1. **Start button**

   - Create a session row with `started_at = now()` and a tentative `status = "running"`.
   - Store the intended scope (e.g., `project_id`, `user_id`, or `api_key_id`) so you can filter usage accordingly.

2. **Stop button**

   - Update `ended_at = now()`. Compute `t_start` → `t_end`.
   - Call Usage API with `bucket_width=1m` (or `1h` if the session is long) and `group_by=["model"]` plus your scoping fields.
   - Aggregate tokens per model; compute cost using the pricing map.
   - Save the estimate to the session row and return a summary JSON to the UI.

3. **(Optional) Reconcile nightly**

   - Call Costs API for yesterday/today (1d buckets) grouped by `project_id` and compare to the sum of session estimates for sanity checks.

---

## 6) Minimal backend examples

Below are slim, copy‑pastable endpoints. Replace `getAdminKey()` and `pricingFor(model)` with your own implementations, and add auth/validation.

### Node (Express)

```js
import express from "express";
import fetch from "node-fetch";

const app = express();
app.use(express.json());

function getAdminKey() { return process.env.OPENAI_ADMIN_KEY; }
function pricingFor(model) {
  const p = {
    "gpt-4o-2024-08-06": { input: 2.5, output: 5.0 },
    "gpt-4o-mini-2024-07-18": { input: 0.5, output: 1.5 }
  }[model];
  return p || { input: 0, output: 0 };
}

app.get("/api/session-estimate", async (req, res) => {
  const { start, end, project_id, user_id, api_key_id } = req.query;
  const params = new URLSearchParams({
    start_time: String(Math.floor(Number(start))),
    end_time: String(Math.floor(Number(end))),
    bucket_width: "1m",
    group_by: "model"
  });
  if (project_id) params.append("project_ids", project_id);
  if (user_id) params.append("user_ids", user_id);
  if (api_key_id) params.append("api_key_ids", api_key_id);

  const r = await fetch(`https://api.openai.com/v1/organization/usage/completions?${params}`, {
    headers: { Authorization: `Bearer ${getAdminKey()}` }
  });
  if (!r.ok) {
    const text = await r.text();
    return res.status(502).json({ error: `OpenAI Usage API error: ${r.status}`, details: text });
  }
  const buckets = (await r.json()).data || [];

  // Aggregate tokens per model
  const byModel = {};
  for (const b of buckets) {
    for (const row of (b.results || [])) {
      const m = row.model || "(unknown)";
      byModel[m] ??= { input: 0, output: 0, cached: 0, requests: 0 };
      byModel[m].input   += row.input_tokens || 0;
      byModel[m].output  += row.output_tokens || 0;
      byModel[m].cached  += row.input_cached_tokens || 0;
      byModel[m].requests += row.num_model_requests || 0;
    }
  }

  // Compute $ from pricing map
  let total = 0;
  const breakdown = Object.entries(byModel).map(([model, t]) => {
    const price = pricingFor(model);
    const inputCost  = (t.input  / 1000) * price.input;
    const outputCost = (t.output / 1000) * price.output;
    const cost = inputCost + outputCost; // extend if you price cached/audio tokens
    total += cost;
    return { model, ...t, cost_usd: Number(cost.toFixed(6)) };
  });

  res.json({ start: Number(start), end: Number(end), total_usd: Number(total.toFixed(6)), breakdown });
});

app.listen(3000);
```

### Python (FastAPI)

```python
from fastapi import FastAPI
import os, time, httpx

app = FastAPI()
OPENAI_ADMIN_KEY = os.environ.get("OPENAI_ADMIN_KEY")

PRICING = {
    "gpt-4o-2024-08-06": {"input": 2.5, "output": 5.0},
    "gpt-4o-mini-2024-07-18": {"input": 0.5, "output": 1.5},
}

@app.get("/session-estimate")
async def session_estimate(start: int, end: int, project_id: str | None = None):
    params = {
        "start_time": str(start),
        "end_time": str(end),
        "bucket_width": "1m",
        "group_by": "model",
    }
    if project_id:
        params["project_ids"] = project_id

    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.openai.com/v1/organization/usage/completions",
            headers={"Authorization": f"Bearer {OPENAI_ADMIN_KEY}"},
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json().get("data", [])

    by_model = {}
    for bucket in data:
        for row in bucket.get("results", []):
            m = row.get("model") or "(unknown)"
            s = by_model.setdefault(m, {"input": 0, "output": 0, "cached": 0, "requests": 0})
            s["input"] += row.get("input_tokens", 0)
            s["output"] += row.get("output_tokens", 0)
            s["cached"] += row.get("input_cached_tokens", 0)
            s["requests"] += row.get("num_model_requests", 0)

    total = 0.0
    breakdown = []
    for model, t in by_model.items():
        price = PRICING.get(model, {"input": 0, "output": 0})
        cost = (t["input"]/1000)*price["input"] + (t["output"]/1000)*price["output"]
        total += cost
        breakdown.append({"model": model, **t, "cost_usd": round(cost, 6)})

    return {"start": start, "end": end, "total_usd": round(total, 6), "breakdown": breakdown}
```

---

## 7) UI sketch (pseudo‑code)

```tsx
function SessionWidget() {
  const [start, setStart] = useState<number|null>(null);
  const [summary, setSummary] = useState(null);

  const onStart = () => setStart(Math.floor(Date.now()/1000));

  const onStop = async () => {
    const end = Math.floor(Date.now()/1000);
    const resp = await fetch(`/api/session-estimate?start=${start}&end=${end}`);
    const data = await resp.json();
    setSummary(data);
  };

  return (
    <Card>
      <Button onClick={onStart} disabled={!!start}>Start</Button>
      <Button onClick={onStop} disabled={!start}>Stop & Calculate</Button>
      {summary && (
        <div>
          <div>Estimated cost: ${'{'}summary.total_usd.toFixed(4){'}'}</div>
          {/* Render breakdown table by model */}
        </div>
      )}
    </Card>
  );
}
```

---

## 8) Scoping & accuracy tips

- **Scope your query** so you only count the session’s traffic (choose one):
  - Use a **dedicated API key per session** and filter by `api_key_id`.
  - Or use a **project per app** and filter by `project_ids`.
  - Or tag requests with `user_id` and filter by `user_ids`.
- **Short sessions (< 1 min):** use `bucket_width=1m`; the first/last minute are inclusive—display a small disclaimer.
- **Model switches:** grouping by `model` guarantees correct per‑model pricing.
- **Cache/Audio tokens:** if you rely on caching or audio, incorporate those token classes and prices.
- **Reconciliation:** compare daily totals to the Costs API as a sanity check (differences may appear due to bucket granularity and timing delays).

---

## 9) Error handling & rate limits

- Expect brief delays before usage appears; retry with backoff if a fresh session returns empty.
- Handle pagination via `next_page` when `limit` is small and the window is large.
- Respect organization limits/rate limits; surface a friendly message if the usage endpoint returns 429.

---

## 10) Security

- Keep the Admin key in server‑side env vars.
- Add auth to your session endpoints and avoid exposing group IDs or key IDs in the client.
- Log raw token totals **server‑side**; store only derived totals client‑side if you need to minimize sensitive metadata.

---

## 11) Test checklist

-

---

## 12) Drop‑in cURL sanity check

```bash
# Tokens by minute for the last 30 minutes, grouped by model
curl -s -H "Authorization: Bearer $OPENAI_ADMIN_KEY" \
  "https://api.openai.com/v1/organization/usage/completions?start_time=$(($(date -u +%s)-1800))&bucket_width=1m&group_by=model" \
  | jq .

# Daily costs for the last day (for reconciliation)
curl -s -H "Authorization: Bearer $OPENAI_ADMIN_KEY" \
  "https://api.openai.com/v1/organization/costs?start_time=$(($(date -u +%s)-86400))&bucket_width=1d&limit=2" \
  | jq .
```

---

## 13) Implementation notes

- Timestamps are **UTC**.
- `group_by` must include the fields you want back (otherwise they’ll be `null`).
- The Costs API currently supports `bucket_width=1d` only; don’t try to use it for minute‑level sessions.
- Keep your pricing map in sync with the official pricing page.

---

**End of doc.**

