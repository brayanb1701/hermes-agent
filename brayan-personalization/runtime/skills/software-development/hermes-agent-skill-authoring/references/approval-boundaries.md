# Approval boundaries for skill edits

Session lesson: when Brayan asks for an analysis such as “how would you fix this skill?”, do not immediately modify the skill. He expects a proposed diagnosis and restore/patch plan first, then explicit approval before edits.

Apply this to skill-library work:

- Treat “analyze”, “review”, “how would you fix”, “what would you change”, and “tell me the plan” as read-only by default.
- It is acceptable to inspect skills, linked files, git history, session history, and candidate restore points.
- Do not call `skill_manage(action='patch'|'edit'|'write_file'|'remove_file')` unless the user explicitly asks to update/fix/apply/save, or the current user message is a standing instruction to update the skill library.
- If a previous mistake requires repair, report the exact candidate source and wait unless the user explicitly authorizes restoration.
- If the user explicitly asks to “update the skill library” after a correction, then act: patch the relevant class-level skill with the workflow lesson.

Good response shape for read-only review:

1. What is wrong.
2. What should be kept.
3. What should be removed or moved elsewhere.
4. Candidate restore point or patch outline.
5. Ask for approval before applying changes.
