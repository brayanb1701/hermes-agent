---
name: opportunity-live-source-checks
description: Verify whether saved job/opportunity URLs are still live, especially when dashboards or recommendation agents depend on current posting state.
version: 1.0.0
author: Darwin
license: MIT
---

# Opportunity Live Source Checks

Use this skill when a recommendation, opportunity-preparation run, closeout decision, or dashboard review depends on whether a saved job, fellowship, grant, scholarship, challenge, bounty, or application URL is still live.

## Goal

Produce a small evidence-backed live-source finding, not a broad web research report. The output should let Darwin decide whether to keep, pivot, demote, or mark an opportunity as `user-status-needed` without inventing final states.

## Procedure

1. **Start from the saved source.**
   - Inspect the opportunity record for `source_url`, `application_url`, host/platform, role title, company/program, and expected title text.
   - If the user provided a direct URL, check that original URL before relying on search or old session memory.

2. **Do the smallest non-interactive live check that answers the question.**
   - Record method, HTTP status, final redirected URL, byte count or response size, and whether expected role/title text was present.
   - For simple pages, a direct HTTP fetch is usually enough.
   - For JavaScript-heavy pages, use browser/web extraction only if the direct check is inconclusive and the decision warrants it.

3. **Do not treat HTTP 200 as sufficient evidence of a live role.**
   - A platform can return HTTP 200 for a generic company page, soft-404 page, or stale shell page.
   - Require expected title/role/program text or API evidence of current listings.
   - If a saved direct job URL returns HTTP 200 but the expected title is absent, call it stale/ambiguous rather than live.

4. **Handle Workable carefully.**
   - Saved `https://apply.workable.com/<subdomain>/j/<shortcode>/` URLs can redirect to a company jobs page, a `?not_found=true` page, or a generic page even while related roles remain live under new shortcodes.
   - Query the company API before recommending demotion:
     - `POST https://apply.workable.com/api/v3/accounts/<subdomain>/jobs` with JSON `{}`.
     - If useful, also check `GET https://apply.workable.com/api/v2/accounts/<subdomain>/jobs/departments?all=true`.
   - If a bare request returns `403 Forbidden`, retry with browser-like headers:
     - `Accept: application/json, text/plain, */*`
     - `Content-Type: application/json`
     - `User-Agent: Mozilla/5.0 ...`
     - `Origin: https://apply.workable.com`
     - `Referer: https://apply.workable.com/<subdomain>/`
   - Record API status, endpoint, total job count, matching titles, shortcodes, published dates, and replacement URLs.
   - For replacement direct URLs, also check whether the expected title text appears. If an old replacement URL returns HTTP 200 but title text is absent and the API no longer lists it, do not recommend it as current.

5. **Convert evidence into a conservative recommendation.**
   - If exact role is live: keep/recommend current action and cite the exact URL/shortcode.
   - If exact role is stale but equivalent roles are live: pivot the packet/recommendation to current matching titles and shortcodes.
   - If source is inaccessible: say inaccessible with method/status; do not claim expired.
   - If deadline/posting has passed and no submission evidence exists: recommend `unknown` or `user-status-needed`, not an invented submitted/skipped state.

## Output shape

Use concise bullets:

- Source checked: `<url>`
- Method: direct HTTP / API / browser / search
- Status: HTTP code + final URL
- Expected title present: yes/no
- Current matches: title, shortcode, published date, URL
- Decision implication: keep / pivot / demote / needs user-status evidence

## Pitfalls

- Do not generalize a transient fetch failure into “the platform is broken.” Retry with a different request shape first.
- Do not infer no prior submission from absence of vault evidence; use `unknown` or `user-status-needed` unless there is explicit proof.
- Do not let stale saved URLs hide current replacement roles on the same platform.
- Do not keep recommending broad scouting when the live check has narrowed the action to a small apply-vs-proof or closeout-status decision.
