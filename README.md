# Reflect

**Live Demo:** [https://yogyam-fitnessreflect.vercel.app/](https://yogyam-fitnessreflect.vercel.app/)  
**Backend:** Hosted via AWS EC2.

Reflect is a RAG-enabled LiveKit voice agent that acts as an evening fitness accountability coach. It logs daily metrics (steps, calories, protein, workout notes) through natural voice conversation, compares them against historical entries via retrieval-augmented generation, and persists each session into a growing fitness journal.

## System Architecture

### Backend

- **LiveKit Agent** (`agent/main.py`): A `VoicePipelineAgent` using OpenAI plugins for STT (Whisper), LLM (GPT-4o-mini), and TTS. VAD is handled by Silero.
- **RAG Retriever** (`agent/rag.py`): Uses ChromaDB as the local vector store and OpenAI `text-embedding-3-small` for embeddings. The retriever is loaded during the agent's `prewarm` phase and queried via the `search_fitness_journal` tool call whenever the LLM needs historical context.
- **Journal Tool** (`agent/journal_tool.py`): A tool call that appends the user's daily entry to the markdown log, regenerates the PDF, and re-ingests it into the vector store in a single pass. This means the RAG context is always up to date within the same session.
- **System Prompt** (`agent/prompts.py`): Instructs the agent to gather metrics conversationally (not all at once), compare against past days using the retrieval tool, and call the logging tool before ending the session.

### Frontend

- **Next.js React client** (`frontend/`): Single-page app with Start Call / End Call buttons and a live transcript panel that updates via LiveKit's `TranscriptionReceived` event.
- **History Graph**: A Recharts line chart that renders steps, calories, and protein over time by parsing the markdown log via an API route (`/api/history`). The graph refreshes automatically when the user ends a call, so newly logged data appears immediately.
- **Token Route** (`frontend/app/api/token/route.ts`): Issues LiveKit access tokens server-side using the LiveKit Server SDK.

### RAG Integration

The RAG document is `data/fitness-log.md`, a structured markdown file containing:
- A fitness profile section (height, weight, body fat estimate, caloric targets, protein floor).
- Daily log entries in a fixed schema: `Steps: X. Calories: Y kcal. Protein: Zg. Reflection: ...`

The ingestion pipeline works as follows:
1. `scripts/generate_pdf.py` converts the markdown into a multi-page PDF using raw PDF stream construction (no external PDF libraries).
2. `scripts/ingest_pdf.py` extracts text from the PDF using `pypdf`, chunks it by page, embeds each chunk with OpenAI, and upserts into a ChromaDB collection.
3. The `log_daily_reflection` tool call triggers both scripts automatically after appending a new entry, so the vector store stays current.

To test the RAG system, ask the agent a question that requires historical lookup, such as:
- "How did my steps today compare to last week?"
- "Have I been hitting my protein targets consistently?"
- "Would you say I have been on track with losing weight?"

The agent will retrieve the relevant past entries and the fitness profile from the vector store before answering.

### Tool Calls

The agent exposes two tool calls to the LLM:

| Tool | Purpose |
|------|---------|
| `search_fitness_journal` | Queries the ChromaDB vector store to retrieve past daily entries or profile facts. |
| `log_daily_reflection` | Appends the current day's metrics to the markdown log, rebuilds the PDF, and re-ingests embeddings. |

## Tools and Frameworks Used

- LiveKit Agents SDK (Python) for the voice pipeline
- LiveKit Client SDK (JS) for the frontend room connection
- OpenAI API for STT, LLM, TTS, and embeddings
- Silero VAD for voice activity detection
- ChromaDB for the local vector store
- Next.js 14 for the React frontend
- Recharts for the history visualization
- pypdf for PDF text extraction

## Local Setup

1. Copy `.env.example` to `.env` and fill in `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, and `OPENAI_API_KEY`.
2. Install Python dependencies: `pip3 install -r agent/requirements.txt`
3. Install frontend dependencies: `cd frontend && npm install`
4. Generate the PDF and ingest it:
   ```
   python3 scripts/generate_pdf.py data/fitness-log.md data/fitness-log.pdf
   python3 scripts/ingest_pdf.py data/fitness-log.pdf
   ```
5. Start the frontend: `cd frontend && npm run dev`
6. Start the agent (from the repo root): `PYTHONPATH=. python3 -m agent.main dev`

The frontend runs on `http://localhost:3000`. The agent connects to the LiveKit Cloud room automatically when a user starts a call.

## Design Decisions and Trade-offs

- **Local ChromaDB instead of a hosted vector DB**: Chosen for simplicity and zero external dependencies beyond the OpenAI API. The dataset is small enough that local persistence is sufficient.
- **Markdown as the source of truth**: The fitness log is a plain markdown file rather than a database. This keeps the demo transparent (you can open the file and read it) and simplifies the PDF generation pipeline.
- **Re-ingestion on every log**: After each tool call, the entire PDF is regenerated and re-ingested. This is acceptable for a small document but would not scale to thousands of entries. A production system would use incremental upserts.
- **No oven, no problem**: The PDF generation script builds valid PDF files from scratch using raw PDF stream commands and built-in Type1 fonts. No `reportlab` or `weasyprint` dependency is needed.
- **STT model**: Using Whisper via the OpenAI API. The LiveKit OpenAI plugin handles chunking and streaming internally.
- **Chunking strategy**: The `ingest_pdf.py` script was custom-written with a regex to chunk the document precisely by each `## Day` header, rather than arbitrarily by page. This ensures the RAG retriever fetches exact, neatly-segmented daily logs.
- **Hosting assumptions**: Built under the assumption that the agent and frontend could run in isolated environments (AWS EC2 worker vs. Vercel serverless). However, because the RAG pipeline utilizes local files (`fitness-log.md`), true end-to-end synchronization of the frontend graph in production requires hosting the Next.js app on the same EC2 instance.


## Acknowledgements
I used Claude to discuss the idea at first. Then I used Antigravity to code out the frontend and backend, and it helped guide me to hosting the LiveKit Agent through AWS EC2.
