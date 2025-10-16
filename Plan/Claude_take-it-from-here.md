# Handoff: State of Local LLM + RAG (Backend + UI)

This is a straight handoff on where things stand, what works, what doesn’t, how to reproduce, and the shortest path to finish. It also includes the missteps on my side and why I’m out.

## TL;DR
- Backend exists and runs (FastAPI). Core endpoints are in place: `/health`, `/ingest`, `/documents`, `/query`, `/logs/ingest`, `/logs/query`, and an SSE stream at `/events/ingest`.
- Ingestion: PDF → text (PyMuPDF) → optional VLM OCR on low/no text (OpenAI `gpt-5-mini`) → chunk → embeddings (LM Studio) → ChromaDB → citations.
- UI exists (Vite + React + Mantine) and calls live endpoints. It includes Health, Documents (with Ingest button), Queries, Logs, Settings.
- Where we’re stuck: The frontend does not visibly reflect ingest activity. Logs show little useful info, and Chroma telemetry spam initially obscured the signal. I added SSE + activity summary, but it still isn’t surfacing progress on your side.

## Environment I targeted
- Windows 11, Python 3.11, LM Studio on `http://localhost:1234`.
- PDFs under `training_data`.
- Embeddings model id: `text-embedding-qwen3-embedding-4b`.
- Backend runs on `uvicorn server.app:app --reload`.
- Frontend dev on port 5174 by default (`web/`).

## What’s built (and where)
- Backend (FastAPI):
  - `server/app.py` — FastAPI app, CORS enabled for UI, endpoints.
  - `server/ingest.py` — ingestion orchestrator (PyMuPDF, OCR trigger, embeddings, upsert, event + log writers).
  - `server/retrieval.py` — builds context, asks LM, returns answer + citations.
  - `server/vector_store.py` — Chroma client (telemetry disabled) with fallback simple store.
  - `server/clients/` — `lmstudio.py` (embeddings + chat), `openai_vlm.py` (OCR via `gpt-5-mini`).
  - `server/event_log.py` — JSONL logs (ingest/query) under `logs/`.
  - `server/event_bus.py` — in‑process pub/sub for ingest SSE.
  - `server/logging_config.py` — basic app logging (rotating file).
  - `server/settings.py` — reads `.env` (dotenv), defaults for all.
- Frontend (Vite + React):
  - `web/src/App.tsx` — Tabs: Dashboard (health), Documents (ingest + activity), Queries, Logs, Settings.
  - `web/src/api/client.ts` — API client and base URL wiring.
  - `web/src/hooks/useEventSource.ts` — subscribes to `/events/ingest`.

## What works (verified earlier)
- `GET /health` returns OK for LM Studio and (with Chroma installed) DB.
- `POST /ingest` works via raw API: files processed, chunks upserted, `ocr_events` list in response.
- `GET /documents` returns chunk counts by file.
- `POST /query` returns an answer with citations (when data is ingested and LM Studio chat model is set via `LLM_MODEL_ID`).
- Chroma telemetry noise is now silenced (set in env and via client settings). This needs a backend restart to reflect in logs.

## What doesn’t (your current report)
- App log looked unchanged; no visible ingest progress.
- Frontend “Ingest Activity” panel isn’t showing live events or a summary.
- You expected to see current file names and a summary while ingestion is running; currently it doesn’t surface anything on your side.

## Likely causes (triage checklist)
1) SSE connection isn’t open
   - Endpoint: `GET /events/ingest` streams events; UI subscribes via EventSource.
   - CORS: FastAPI configured `UI_ORIGIN=http://localhost:5174`. If UI serves from a different origin/port, backend must be restarted with matching `UI_ORIGIN`.
   - Verify SSE manually: `curl -N http://127.0.0.1:8000/events/ingest` (should hang and print `data: {...}` when ingest starts).

2) UI not pointing at the right backend
   - UI base defaults to `http://127.0.0.1:8000`. If backend runs elsewhere, set it in the Settings tab or run dev with `VITE_API_BASE`.

3) Ingest returns immediately as “unchanged”
   - The ingestor skips files that haven’t changed (checksum index under `data/ingest_index.json`).
   - Expected events exist for skipped files, but if the SSE stream isn’t connected, the UI will show nothing.

4) Backend logs not showing app activity
   - The app logger is set up, but uvicorn’s reloader + third‑party logs can drown out our lines.
   - Without a restart after disabling telemetry, you’ll still see posthog spam.

5) LM Studio model configuration
   - If `LLM_MODEL_ID` is not set to a loaded chat model in LM Studio, `/query` works poorly or times out; ingestion still runs though.

## How to reproduce and verify (step‑by‑step)
- Backend
  - Ensure `.env` has: `PDF_SOURCE_DIR=training_data`, `LLM_BASE_URL=http://localhost:1234`, `EMBEDDINGS_MODEL_ID=text-embedding-qwen3-embedding-4b`, `LLM_MODEL_ID=<your_chat_model_id>`, `UI_ORIGIN=http://localhost:5174`, `OPENAI_API_KEY=...`.
  - Restart backend: `uvicorn server.app:app --reload`
  - Health: `Invoke-RestMethod http://127.0.0.1:8000/health`
- SSE sanity check
  - Terminal A: `curl -N http://127.0.0.1:8000/events/ingest`
  - Terminal B: `Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ingest -Body '{}' -ContentType 'application/json'`
  - Expect lines like: `data: {"event":"ingest_run_start",...}` followed by file/page events.
- Frontend
  - `cd web && npm install && npm run dev` (default port 5174)
  - In Settings tab: set API base to `http://127.0.0.1:8000` if needed.
  - In Documents: click Ingest; expect the Activity panel to show status `open`, current files, and recently completed.

## Minimal changes Claude should consider (to make it actually visible)
- If SSE fails: add a simple fallback poll of `/logs/ingest` every 1–2s during an ingest session.
- Add an explicit “Re‑ingest (force)” button that clears `data/ingest_index.json` so the pipeline runs regardless of checksums.
- Ensure an obvious ingest summary card (files found, processed, skipped, errors) is returned directly by `/ingest` and shown immediately in UI.
- Add a short heartbeat event every few seconds on `/events/ingest` so the UI can show “connecting/open” reliably and clear stale state.
- Turn up app logging for `server.ingest` to INFO and add one log line per phase.

## Known gotchas
- Chroma telemetry spam (now disabled by default). Requires backend restart to take effect.
- Windows build tooling (MSVC) for `chroma-hnswlib`. We worked around this, then re‑enabled Chroma once Build Tools were installed.
- LM Studio must have both a chat model loaded (`LLM_MODEL_ID`) and the embeddings model serving at `/v1/embeddings`.

## Why I got fired (candid)
- I focused on scaffolding and plumbing (backend endpoints, OCR, embeddings, logging, SSE, UI skeleton) but failed to deliver a visibly working ingestion experience in the UI when you clicked the button. That lack of immediate, tangible feedback undermined confidence.
- I chased environment friction (Windows toolchain, Chroma telemetry, ports, CORS) and made iterative changes without pausing to add a fallback (polling) or a guaranteed summary path that would have shown progress even if SSE or CORS weren’t perfect.
- I should have proved the “click Ingest → see filenames and counts” loop on day one with the simplest approach (no SSE; just show `/ingest` response and `/documents` deltas), then layered in streaming.

## What I would do next (if allowed)
- Implement a fallback poller in the UI for `/logs/ingest` during an ingest run (no code removal; minimal patch).
- Add a `force=true` flag to `/ingest` to clear the checksum index so re‑runs always produce visible events.
- Add a compact summary block to the top of Documents using `/documents` + last `/ingest` response.
- Add a `/health/detail` that validates LM Studio chat/embedding model IDs explicitly and returns friendly messages.

## File map (touchpoints)
- Backend
  - `server/app.py`, `server/ingest.py`, `server/retrieval.py`, `server/vector_store.py`, `server/settings.py`
  - Logs under `logs/`: `app.log`, `ingest.jsonl`, `query.jsonl`
- Frontend
  - `web/src/App.tsx`, `web/src/hooks/useEventSource.ts`, `web/src/api/client.ts`

## Contacts & credentials
- `.env` template in `.env.example` and `sampl.env` (UI origin set to port 5174; LM Studio base on localhost:1234).
- Your `OPENAI_API_KEY` is used only for OCR assist.

Good luck — with two small UI fallbacks (polling + forced re‑ingest) you’ll have visible progress instantly, even if SSE is flaky.
