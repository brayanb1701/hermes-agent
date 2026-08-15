# Airtable interface-form inspection

Use this when a public Airtable URL such as `https://airtable.com/<app-id>/<page-id>/form` returns HTTP 200 but direct extraction exposes only Airtable's generic app shell.

## Validated fallback

Render the original URL with an isolated, disposable headless Chrome profile and dump the hydrated DOM:

```bash
profile="$(mktemp -d)"
timeout 90s google-chrome \
  --headless=new \
  --no-sandbox \
  --disable-gpu \
  --disable-dev-shm-usage \
  --user-data-dir="$profile" \
  --virtual-time-budget=30000 \
  --dump-dom "$URL" > /tmp/airtable-rendered.html
rm -rf "$profile"
```

Then strip scripts/styles and inspect the rendered text for:

- expected opportunity title
- host/recruiter and disclosed client
- responsibilities and qualifications
- location, work mode, hours, compensation, and deadline
- required form fields, uploads, and custom questions
- explicit geographic/work-authorization restrictions

## Evidence standard

Record both layers:

- Direct fetch: HTTP status, final URL, response size, and whether it was only the generic shell.
- Rendered page: DOM size, expected-title presence, extracted form fields, and unresolved unknowns.

A successful hydrated render with the expected title and visible form fields is strong evidence that the opportunity/form is live. HTTP 200 on the shell alone is not.

## Operational notes

- Use an isolated profile rather than modifying or depending on the user's normal Chrome session.
- Do not submit the form; inspection remains read-only.
- Preserve unknowns explicitly. A visible country-of-residence field does not by itself prove a country restriction.
- If Chrome is unavailable, use another browser-based renderer; do not label the posting stale merely because direct HTTP extraction returned a shell.
