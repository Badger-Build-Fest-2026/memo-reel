# Contributing to Memo Reel

## Development setup

1. Copy `env.example` to `.env` and configure the required database and Gemini
   credentials.
2. Start Redis, the API, migrations, and the worker:

   ```bash
   docker compose up --build
   ```

3. In a second terminal, start the frontend:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Before opening a change

Run the backend tests from the repository root:

```bash
pytest
```

Build the frontend:

```bash
cd frontend
npm run build
```

Also check the changed files for accidental secrets, generated data, and
platform-specific files such as `.DS_Store`.

## Project conventions

- Keep backend code under `app/`, agent code under `agent/`, and frontend code
  under `frontend/`.
- Add migrations under `migrations/`; do not edit an applied migration.
- Keep generated media, logs, local data, and credentials out of Git.
- Update the root README when setup commands, service URLs, or architecture
  change.
- Prefer focused changes and include a test when changing observable behavior.