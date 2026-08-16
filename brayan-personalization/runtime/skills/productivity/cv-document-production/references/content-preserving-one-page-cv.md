# Content-Preserving One-Page CV Layout

This reference captures a validated pattern for turning a content-heavy technical CV into a readable one-page A4 PDF without altering the user's wording or hierarchy.

## Validated layout

- Full-width name/contact header.
- Full-width professional summary.
- Two-column body.
- Wider left column for experience (roughly 63–65%).
- Narrower right column for education, extra-curricular activities, and skills.
- Organization heading on its own line, followed by the exact role title and date line from the editable source.
- Subtle divider and restrained section rules; no decorative elements that consume space.

## Iteration method

1. Re-read the latest Markdown/source after every user edit.
2. Rebuild or synchronize HTML content before touching CSS.
3. Render PDF and check page count.
4. Extract text and assert exact headings plus representative organization/role pairs.
5. Render the page to an image and inspect the lower margin and both column bottoms.
6. If there is substantial whitespace, increase body font, line height, or spacing incrementally.
7. If a small increase spills to page two, back off one increment; do not remove content.
8. Re-run content assertions after the final render.

## Regression assertions

At minimum, check:

- exact section headings, especially user-edited labels
- exact organization names
- exact role titles
- current dates
- one distinctive bullet from every position
- all skill categories
- page count
- no comment markers or review notes

## Proven failure modes

- Using stale HTML after the Markdown changed.
- Renaming `Experience` to `Relevant Experience` for stylistic reasons.
- Replacing `Extra-Curricular Activities` with a more targeted label without permission.
- Reversing `Organization` and `Role` hierarchy.
- Adding a subtitle below the candidate's name that was not in the source.
- Merging or removing bullets to force one page.
- Accepting a one-page result with large bottom whitespace instead of increasing readability.

## Visual acceptance criteria

- One page when requested and legible.
- Bottom whitespace is a modest print margin, not a large unused band.
- Neither column is visibly sparse relative to the other.
- Dates do not collide with titles.
- No clipped text, overlap, overflow, or orphaned fragments.
- Body text remains readable at normal PDF zoom and print size.
