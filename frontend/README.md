# MemoReel Frontend

Next.js app: a 3D knowledge graph of your saved reels, plus a chat dock
that queries them via RAG.

## Setup

```bash
npm install
cp .env.local.example .env.local
```

Edit `.env.local` if your backend isn't running on `localhost:8000`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

## Run

```bash
npm run dev
```

Open http://localhost:3000?user=jay (the `user` query param picks whose
graph/chat to load - defaults to "demo" if omitted). This matches the
`user_id` you pass to `run_pipeline.py --user-id` on the backend side -
use the same value in both places to see your own reels.

## What's here

- `app/page.tsx` - main view: fetches the graph, filters by category,
  renders the 3D graph + chat dock + detail panel
- `components/KnowledgeGraph.tsx` - the 3D force-directed graph
  (wraps `3d-force-graph`). Click a reel node to open its detail panel;
  click any node to fly the camera to it.
- `components/ChatDock.tsx` - collapsed input that expands into a full
  chat thread when you ask something. Calls `POST /chat` on the backend.
- `components/TopBar.tsx` - logo + category filter chips
- `components/NodeDetailPanel.tsx` - slide-in panel for a selected reel
- `lib/api.ts` / `lib/types.ts` - backend API client + shared types

## Backend requirements

This expects two endpoints from the FastAPI backend in this repository:

- `GET /api/v1/graph?user_id=...` -> `{nodes: [...], edges: [...]}`
- `POST /api/v1/chat` with `{query, user_id}` -> `{answer, sources: [...]}`

Both routes are registered in `app/api/v1/api_endpoints.py`.

Also needs CORS enabled on the backend so the Next.js dev server
(localhost:3000) can call it (localhost:8000) - add to your `main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Known limitation from this build environment

This was built and `next build`-verified in a sandboxed environment
without access to `fonts.googleapis.com`, so the Google Fonts
(`Fraunces`, `IBM Plex Sans`) couldn't be live-fetched here - the build
was verified with a temporary fallback, then the real font imports were
restored before delivery. On your machine, with normal internet access,
`npm run build` / `npm run dev` should fetch them automatically with no
changes needed. If it doesn't, check your network/proxy settings before
assuming it's a code issue.
