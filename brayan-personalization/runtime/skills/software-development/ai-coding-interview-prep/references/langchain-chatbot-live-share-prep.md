# LangChain Chatbot Live Share Prep Reference

This reference captures a concrete preparation pattern from an AI/chatbot engineer interview-prep session.

## Source interview signals

The user had a coding interview for an AI engineer / chatbot engineer role. The interview guidance said:

- mixed cultural + technical interview;
- screen sharing and VS Code Live Share;
- interviewer wants to observe problem-solving approach;
- GenAI tools are allowed;
- they may discuss production-readiness considerations;
- Python 3.13+ recommended;
- optional AI coding assistant: GitHub Copilot or Claude Code;
- JD mentions Azure, GenAI, LangChain and/or Airflow, REST APIs, NLP/evaluation, data pipelines, vector DBs/embeddings, conversational AI.

The client context involved Slalom and Purina, so a realistic exercise class was a consumer-facing pet-care support chatbot rather than LeetCode.

## Interpretation

Most likely exercise shape:

- hosted/shared starter code through VS Code Live Share;
- local tests as the source of truth;
- chatbot intent routing;
- retrieval over local FAQ/KB/product data;
- citations from source IDs;
- deterministic safety/escalation paths;
- FastAPI/Pydantic response model;
- optional LangChain tools/runnables;
- discussion of production Azure architecture.

The key operational uncertainty was whether Brayan’s local prep folder would matter if the code lives in a Live Share workspace. The durable answer: yes, but as a portable context pack. Copy files into the active workspace if possible; otherwise use them as prompt/reference material.

## Concrete folder created in that session

The prep kit was created at:

```text
/home/brayan/tmp_projects/interview_exercise/agent_interview_kit
```

Tracked contents included:

```text
AGENTS.md
CLAUDE.md
README.md
docs/INTERVIEW_INTERPRETATION.md
docs/OFFICIAL_DOCS_AND_SKILLS.md
docs/TIMEBOX_PLAN.md
prompts/codex_prompts.md
prompts/claude_code_prompts.md
scripts/bootstrap_into_workspace.py
scripts/doctor.py
scripts/install_global_fallbacks.py
scripts/run_tests.sh
skills/hermes/*.md
skills/custom/langchain-rag-interview.md
.claude/skills/langchain-rag-interview/SKILL.md
.agents/skills/langchain-rag-interview/SKILL.md
requirements.txt
requirements-optional-vectorstores.txt
pyproject.toml
tests/test_kit_sanity.py
```

## Skills copied into the portable kit

Useful Hermes skills copied for local reference:

- `systematic-debugging`
- `test-driven-development`
- `writing-plans`
- `requesting-code-review`
- `subagent-driven-development`
- `spike`
- `claude-code`
- `codex`

## Skill/search findings

Hermes skills hub searches were run for:

```bash
hermes skills search langchain
hermes skills search rag
hermes skills search azure
hermes skills search chatbot
hermes skills search chroma
hermes skills search faiss
hermes skills search pinecone
hermes skills search qdrant
hermes skills search gradio
hermes skills search fastapi
hermes skills search langgraph
```

Findings:

- No official general LangChain/LangGraph coding skill appeared.
- LangChain results were community/indexed skills, not a single official interview workflow skill.
- Official useful vector/RAG skills found:
  - `official/mlops/chroma`
  - `official/mlops/faiss`
  - `official/mlops/pinecone`
  - `official/mlops/qdrant`
- Azure and FastAPI search results were mostly community-indexed, so official docs are preferred.

## Environment verification from session

The session verified:

- Python available: 3.14.2
- `uv` available
- `claude` CLI available
- `codex` CLI available
- VS Code available
- VS Code version was new enough
- VS Code extensions included Python and Copilot Chat
- Live Share extension was installed and verified
- Python imports passed for pytest, FastAPI, Pydantic, LangChain, LangChain Core, and LangGraph
- kit tests passed
- ruff passed
- bootstrap script copied files successfully into a temp workspace

Do not encode these exact versions as requirements; they were session state. The durable lesson is the `doctor.py` verification pattern.

## Useful first prompt

```text
Inspect the problem statement, tests, and TODOs. Do not edit files yet. Summarize the exact behavior required to pass tests, identify the response schemas/public interfaces we must preserve, and propose the smallest implementation order for a timed interview.
```

## Production-readiness talking points used

- Local lexical retrieval is interview-safe and deterministic.
- Production should use Azure AI Search hybrid/vector retrieval over approved KB articles.
- Azure OpenAI or another approved model should receive only selected retrieved context.
- Add evals for intent accuracy, groundedness, citation coverage, escalation precision/recall, latency, and cost.
- Add tracing with LangSmith or cloud telemetry.
- Keep PII controls, content safety, prompt-injection resistance, and human handoff.
- Keep product eligibility, account actions, and emergency routing deterministic.
