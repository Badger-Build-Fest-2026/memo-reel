# RecallGraph

FastAPI starter for RecallGraph.

## Run locally

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API docs are available at `http://127.0.0.1:8000/docs`.

## Endpoints

- `GET /health` checks that the API is running.
- `POST /api/v1/reels` accepts a `user_id` and an Instagram Reels URL.

Example request:

```sh
curl -X POST http://127.0.0.1:8000/api/v1/reels \
	-H 'Content-Type: application/json' \
	-d '{"user_id":"user-123","reel_url":"https://www.instagram.com/reels/DdjIyezy1Wg/"}'
```

The service currently acknowledges valid submissions; connect persistence or background processing in `app/services/reel_service.py`.