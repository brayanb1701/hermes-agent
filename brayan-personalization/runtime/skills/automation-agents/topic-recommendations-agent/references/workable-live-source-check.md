# Workable live-source check for opportunity recommendations

Use this when a saved Workable opportunity URL appears stale, especially during topic recommendation or opportunity-pressure runs.

## Why

A saved Workable posting URL such as `https://apply.workable.com/<subdomain>/j/<old_shortcode>/` can redirect to the company openings page after that specific posting is retired. That does **not** prove the opportunity lane is dead: the company may have equivalent replacement roles under new shortcodes.

## Minimal check

1. Parse the company subdomain from the saved URL:
   - `https://apply.workable.com/huggingface/j/56232F23CB/` → subdomain `huggingface`.
2. Fetch the saved URL non-interactively and record:
   - HTTP status
   - final redirected URL
   - whether the expected role/title text is present
3. If stale/redirected, list current jobs via the Workable API:

```python
import json, urllib.request
subdomain = "huggingface"
url = f"https://apply.workable.com/api/v3/accounts/{subdomain}/jobs"
payload = json.dumps({}).encode()
req = urllib.request.Request(
    url,
    data=payload,
    method="POST",
    headers={
        "User-Agent": "Mozilla/5.0 HermesTopicRecommendations/1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://apply.workable.com",
        "Referer": f"https://apply.workable.com/{subdomain}/",
    },
)
with urllib.request.urlopen(req, timeout=20) as r:
    data = json.loads(r.read().decode())
print(r.status, url, data.get("total"))
for job in data.get("results", []):
    print(job.get("title"), job.get("shortcode"), job.get("published"), job.get("department"), job.get("workplace"))
```

Optional department discovery:

```text
GET https://apply.workable.com/api/v2/accounts/<subdomain>/jobs/departments?all=true
```

Some accounts use numeric department IDs in API filters. If a relevant department appears, you can filter jobs with a JSON payload such as `{"department": [216968]}`.

## What to record in the vault recommendation/log

- Method: direct Workable API check.
- Endpoint(s) used.
- HTTP status and final redirected URL for the saved posting.
- Total current jobs returned.
- Matching role titles, shortcodes, departments, workplace/location, and published dates.
- Replacement application URLs: `https://apply.workable.com/<subdomain>/j/<shortcode>/`.
- A conservative conclusion:
  - Old saved posting stale, but replacement roles found → recommend updating the opportunity record/packet.
  - No matching roles found → recommend demotion/watch, not final rejection, unless other evidence supports closure.

## Pitfall

Do not conclude “role closed” solely from an old Workable shortcode redirect. Check the company-level jobs API first when the role family still matters.
