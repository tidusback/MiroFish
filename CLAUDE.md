# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MiroFish is a multi-agent AI simulation platform. Users upload seed documents (PDF/MD/TXT), the system builds a knowledge graph from them, generates thousands of AI agent personas, simulates social dynamics on dual platforms (Twitter + Reddit), then produces predictive reports. The full pipeline is: **Graph Build → Environment Setup → Simulation → Report → Interaction**.

## Commands

### Full Dev Setup
```bash
npm run setup:all     # installs frontend (npm) + backend (uv) deps
npm run dev           # runs both backend and frontend concurrently
```

### Individual Services
```bash
npm run backend       # cd backend && uv run python run.py  (Flask on :5000)
npm run frontend      # cd frontend && npm run dev          (Vite on :3000)
npm run build         # cd frontend && npm run build
```

### Backend-only
```bash
cd backend && uv sync            # install/update Python deps
cd backend && uv run python run.py
```

### Docker
```bash
docker compose up -d   # requires .env to be populated
```

### Tests
```bash
cd backend && uv run pytest      # pytest + pytest-asyncio available; no test suite exists yet
```

## Architecture

### 5-Step Pipeline

```
Upload docs → ontology_generator → graph_builder (Zep) → zep_entity_reader
                                                              ↓
                       oasis_profile_generator ← entities → simulation_config_generator
                                                              ↓
                                          simulation_manager → simulation_runner (OASIS subprocess)
                                                              ↓
                                                       report_agent (ReACT)
                                                              ↓
                                                       interview / export
```

### Backend (`backend/app/`)

**API layer** (`api/`) — three Flask blueprints:
- `graph.py`: upload files, trigger graph build, poll task status
- `simulation.py`: read entities, generate profiles/config, start simulation
- `report.py`: generate report, handle interview turns, export HTML/PDF

**Service layer** (`services/`) — each service owns one pipeline stage:
| Service | Responsibility |
|---|---|
| `ontology_generator.py` | LLM → JSON entity/relationship schema |
| `graph_builder.py` | chunks text → builds Zep knowledge graph (async task) |
| `zep_entity_reader.py` | queries graph → filtered entity list |
| `oasis_profile_generator.py` | entities → agent persona JSON |
| `simulation_config_generator.py` | entities → OASIS simulation parameters |
| `simulation_manager.py` | orchestrates dual-platform (Twitter + Reddit) parallel runs |
| `simulation_runner.py` | launches OASIS subprocess, monitors via IPC queue |
| `report_agent.py` | ReACT loop: reason → call zep_tools → synthesize report |
| `zep_tools.py` | search abstractions: InsightForge, PanoramaSearch, QuickSearch |

**Models** (`models/`): `ProjectManager`/`TaskManager` are in-memory singletons tracking project state and async task status. All background work (graph building, simulation) is dispatched as `threading.Thread` with task IDs returned immediately to the frontend.

**Simulation IPC**: `simulation_runner.py` launches OASIS as a subprocess and exchanges JSON messages via `simulation_ipc.py`. This is the critical concurrency boundary — don't mix threading primitives across it.

### Frontend (`frontend/src/`)

Vue 3 + Composition API. The workflow steps map directly to components: `Step1GraphBuild.vue` through `Step5Interaction.vue`, composed in `MainView.vue`. D3.js powers the graph visualization in `GraphPanel.vue`. API calls go through `src/api/` (Axios with exponential backoff retry).

### Configuration

All backend settings live in `backend/app/config.py` and are loaded from `.env` at the project root. Copy `.env.example` to `.env` and set at minimum:
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` — OpenAI-compatible endpoint (default: Alibaba Qwen-plus)
- `ZEP_API_KEY` — Zep Cloud knowledge graph
- `ZEP_USER_ID` — Zep user namespace

### Localization

Backend translations live in `locales/` (7 languages: zh, en, es, fr, pt, ru, de). Use `t('key', **kwargs)` from `backend/app/utils/locale.py`. Frontend uses `vue-i18n` with matching keys. Add new strings to all locale files together.

## Key Conventions

- **Entity type names** are auto-normalized to PascalCase via `_to_pascal_case()` in `ontology_generator.py` — don't bypass this.
- **API responses** follow `{"success": bool, "data": ..., "error": ...}` — maintain this shape in all new endpoints.
- **Async tasks**: return a `task_id` immediately, let clients poll `GET /api/graph/task/<task_id>`. Don't block Flask request threads for long operations.
- **LLM calls** go through `backend/app/utils/llm_client.py` — use its retry/timeout wrapper rather than calling `openai` directly.
- Python: `snake_case` files/functions, `PascalCase` classes. Vue: `PascalCase` component files, `camelCase` variables.
