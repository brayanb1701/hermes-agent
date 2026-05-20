---
name: ai-coding-interview-prep
description: Prepare and operate a portable agent-assisted setup for timed AI/chatbot/backend coding interviews, especially VS Code Live Share sessions where Codex, Claude Code, Copilot, or similar tools are allowed.
version: 1.0.0
author: Darwin
license: MIT
metadata:
  hermes:
    tags: [interview, coding-interview, ai-assisted-development, codex, claude-code, live-share, langchain, chatbot, rag, fastapi]
    related_skills: [claude-code, codex, systematic-debugging, test-driven-development, writing-plans, requesting-code-review]
---

# AI Coding Interview Prep

Use this skill when Brayan is preparing for, practicing, or entering a timed coding interview where AI coding assistants are allowed or expected. It is especially relevant for AI engineer / chatbot engineer interviews involving VS Code Live Share, Python, LangChain/LangGraph, FastAPI, RAG, retrieval, citations, safety routing, or production-readiness discussion.

## Goals

Build a portable, low-friction setup that lets Brayan use agents effectively without wasting interview time on tooling:

- repo-local `AGENTS.md` for Codex/OpenAI-style agents;
- repo-local `CLAUDE.md` for Claude Code;
- optional local `.claude/skills/...` and `.agents/skills/...` custom skills;
- prompt snippets for bounded AI-assisted workflow;
- a ready Python virtualenv with likely dependencies;
- a bootstrap script to copy instructions into a newly provided exercise workspace;
- clear guidance for VS Code Live Share constraints.

## Important Live Share interpretation

If the interviewer says Brayan will join a VS Code Live Share link as a guest with editing permissions, assume the actual code may live in the interviewer’s hosted/shared workspace, not in Brayan’s local prep folder.

Implications:

1. Local `AGENTS.md` / `CLAUDE.md` in a prep folder do not automatically affect agents launched from a different shared workspace.
2. The prep folder is still useful as a portable context pack.
3. If allowed and technically possible, copy `AGENTS.md`, `CLAUDE.md`, and custom skills into the exercise workspace root.
4. If the shared workspace is remote/locked down and cannot be reached by local terminal tools, keep the prep folder open as a reference and paste prompt snippets manually.
5. Avoid spending interview time on global configuration unless it is already prepared and verified.

## Preferred setup shape

Create one portable folder such as `agent_interview_kit/` with this structure:

```text
agent_interview_kit/
  AGENTS.md
  CLAUDE.md
  README.md
  pyproject.toml
  requirements.txt
  requirements-optional-vectorstores.txt
  docs/
    INTERVIEW_INTERPRETATION.md
    TIMEBOX_PLAN.md
    OFFICIAL_DOCS_AND_SKILLS.md
  prompts/
    codex_prompts.md
    claude_code_prompts.md
  scripts/
    bootstrap_into_workspace.py
    doctor.py
    install_global_fallbacks.py
    run_tests.sh
  skills/
    hermes/
    custom/
  .claude/
    skills/<interview-skill>/SKILL.md
    settings.json
  .agents/
    skills/<interview-skill>/SKILL.md
  .venv/
```

Initialize it as a git repo and commit the tracked prep artifacts. Ignore `.venv`, caches, `.env`, backups, and bytecode.

## `AGENTS.md` / `CLAUDE.md` content rules

For timed interviews, both files can usually contain the same instructions. Keep them direct and operational:

- inspect problem, tests, and TODOs before editing;
- produce a short plan first;
- make one small patch at a time;
- run narrow tests after each patch;
- debug by reading full errors and tracing root cause;
- preserve response schemas/public interfaces;
- avoid external API calls unless explicitly required;
- keep tests deterministic with fakes/stubs when possible;
- keep safety/business routing deterministic;
- for RAG, cite only retrieved source IDs;
- never add secrets or destructive commands;
- finish with what changed, tests run, and production tradeoffs.

For chatbot/RAG interviews, include defaults:

- deterministic routing before dynamic agents;
- retrieve first, generate second;
- use LangChain/LangGraph only where it clarifies orchestration or is explicitly required;
- use FastAPI/Pydantic models for clear API contracts;
- explain production path: Azure OpenAI or approved LLM, Azure AI Search hybrid/vector retrieval, evals, tracing, privacy, content safety, human handoff.

## Bootstrap script pattern

Add a script that copies the portable instructions into a target exercise workspace:

```bash
python scripts/bootstrap_into_workspace.py /path/to/interview/workspace
python scripts/bootstrap_into_workspace.py /path/to/interview/workspace --force
```

The script should copy at minimum:

- `AGENTS.md`;
- `CLAUDE.md`;
- `.claude/skills/<skill>/SKILL.md`;
- `.agents/skills/<skill>/SKILL.md`.

If overwriting, create `.bak` backups first.

## Doctor script pattern

Add a `doctor.py` script that verifies the setup without requiring network calls:

- Python executable/version;
- `uv`, `claude`, `codex`, `code`, `git` availability;
- VS Code extensions if `code` is present:
  - Live Share;
  - Copilot/Copilot Chat if expected;
  - Python extension;
- imports for likely Python packages:
  - pytest;
  - FastAPI;
  - Pydantic;
  - LangChain/LangChain Core;
  - LangGraph;
- existence of `AGENTS.md`, `CLAUDE.md`, and custom skill files.

Run and report the doctor output before considering setup complete.

## Python environment

For AI/chatbot/backend interviews, a useful base `requirements.txt` is:

```text
pytest
ruff
mypy
fastapi
uvicorn[standard]
pydantic
httpx
python-dotenv
langchain
langchain-core
langchain-community
langgraph
```

Create and verify:

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
python scripts/doctor.py
python -m pytest -q
python -m ruff check .
```

Keep optional vector-store/cloud dependencies in a separate file, not the default install, because some packages may be slow, unnecessary, or incompatible with the newest Python during an interview:

```text
chromadb
faiss-cpu
qdrant-client
pinecone
openai
azure-search-documents
azure-identity
```

## Official-sources preference

When searching for interview-useful skills or docs:

1. Prefer official docs from the framework/company.
2. Prefer official Hermes hub skills when available.
3. Treat community/indexed skills as optional references, not first-line authorities.
4. Do not waste live interview time installing community skills unless they are clearly allowed and necessary.

High-yield official docs to collect for AI/chatbot interviews:

- LangChain overview, agents, tools, retrievers;
- LangGraph workflows/agents and memory;
- Azure OpenAI / Microsoft Foundry;
- Azure AI Search RAG and hybrid search;
- Codex CLI, AGENTS.md, skills;
- Claude Code docs, skills, VS Code integration;
- FastAPI and Pydantic docs.

Useful official vector-store skills, if available in the Hermes hub:

- Chroma for local/open-source RAG prototyping;
- FAISS for pure high-performance vector similarity;
- Qdrant for production vector search;
- Pinecone for managed vector DB.

## Live workflow during interview

Opening line:

> Since AI tools are allowed for this session, I’ll use them transparently as a pair-programmer. I’ll ask for small patches, inspect the diff, run tests, and explain the reasoning myself.

Default first prompt to agent:

```text
Inspect the problem statement, tests, and TODOs. Do not edit files yet. Summarize the exact behavior required to pass tests, identify the response schemas/public interfaces we must preserve, and propose the smallest implementation order for a timed interview.
```

Then proceed with bounded prompts:

```text
Implement only the next smallest slice: <slice>. Preserve public interfaces and test contracts. Do not add external API calls. After editing, run the narrowest relevant test and explain failures before patching.
```

Avoid vague prompts like “build the whole chatbot.”

## 40-minute timebox

- 0–3 min: read prompt/tests and clarify one assumption if needed.
- 3–7 min: run baseline tests and identify failing feature groups.
- 7–25 min: implement core behavior in thin slices.
- 25–33 min: fix failures using systematic debugging.
- 33–37 min: full tests, diff review, remove debug noise.
- 37–40 min: explain production-readiness tradeoffs.

## Verification checklist

Before telling Brayan the kit is ready:

- [ ] `AGENTS.md` exists.
- [ ] `CLAUDE.md` exists.
- [ ] custom interview skill exists under `.claude/skills/...` and optionally `.agents/skills/...`.
- [ ] `scripts/bootstrap_into_workspace.py` was tested against a temporary directory.
- [ ] `.venv` was created and dependencies installed.
- [ ] `scripts/doctor.py` passes.
- [ ] `pytest` passes.
- [ ] `ruff check .` passes or documented exceptions are explained.
- [ ] VS Code Live Share is installed or a concrete install command is provided.
- [ ] Git repo is initialized and prep artifacts are committed.

## Pitfalls

- Do not assume local prep files affect a Live Share workspace hosted elsewhere.
- Do not install global agent instructions by default; make it explicit and backup existing global files.
- Do not overfit to one practice exercise; keep `AGENTS.md` class-level and portable.
- Do not put environment-specific failures into persistent instructions; capture only the durable setup/fix pattern.
- Do not turn optional vector-store/cloud packages into default dependencies unless the actual exercise requires them.
- Do not let AI usage look hidden. Transparency is a positive signal when the interview explicitly allows GenAI tools.

## Session-specific reference

For a concrete LangChain/Purina-style chatbot interview prep kit created during a prior session, see `references/langchain-chatbot-live-share-prep.md`.
