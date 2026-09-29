# Memo Reel

*We consume an enormous amount of useful information through short-form content, especially Instagram Reels, but most of it disappears into an endless feed. A few weeks later, it's nearly impossible to find again.*

**Memo Reel** is a browser extension and AI pipeline that lets you save an Instagram Reel with a single click, extracting what's spoken and shown, and transforming it into a structured, searchable, and interconnected knowledge graph. 

Stop losing ideas to the algorithm. Ask questions, explore your visual graph in Obsidian, and retrieve any idea exactly when you need it.

[![Devpost](https://img.shields.io/badge/Devpost-Memo_Reel-003E54?style=for-the-badge&logo=devpost)](https://devpost.com/software/recallgraph-gyhz7u#submission-history)

## 🎬 Watch the Demo

*(Note: Upload your MP4 to the repo in an `assets/` folder, then this native video player will render it directly on the GitHub page)*

<video src="assets/demo.mp4" controls="controls" style="max-width: 100%;">
  Your browser does not support the video tag.
</video>

## Tech Stack

* **Ingestion:** Chrome Extension, Python 3.11, yt-dlp
* **Processing Pipeline:** FastAPI, Celery, Redis, OpenCV, Whisper
* **Knowledge Extraction & Reasoning:** Gemini (Flash & Flash-Lite), LangGraph, ReAct Agent Loop
* **Context Enrichment:** Fast MCP (fetching and summarizing external GitHub & product links)
* **Data Storage:** Databricks PostgreSQL (Lakebase), NetworkX (Graph topology), ChromaDB (Vector Search)
* **Frontend & Visualization:** Streamlit (Carousel/3D UI), Obsidian (Markdown integration)
* **Infrastructure:** Docker, Docker Compose

## How It Works (The Pipeline)

1. **One-Click Ingestion:** Click "Memorise" on our Chrome extension while watching an Instagram Reel. The URL and metadata are sent to the backend.
2. **Multimodal Extraction:** A Celery worker downloads the video, extracting audio transcripts, visual frames, and text metadata.
3. **Knowledge Graph Generation (GraphRAG):** Gemini categorizes the content, identifying core concepts, entities, and links. A JSON payload is generated and stored in Databricks PostgreSQL.
4. **Context Enrichment (MCP):** A custom Model Context Protocol (MCP) tool crawls and summarizes external product and GitHub links found in the Reels.
5. **Interactive Exploration:** The processed knowledge translates into an Obsidian Vault (`.md` files) and an interactive 3D Streamlit UI. Users can use our LangGraph ReAct agent to chat with their graph with strict subcategory retrieval isolation.

## Agent Configuration & Retrieval Scoping

The GraphRAG agent (`agent/langgraph_agent.py`) intelligently manages Gemini model fallbacks to handle rate limits without dropping queries.

A strict **Retrieval Scoping Guarantee** ensures that queries naming a specific subcategory (e.g., `[[System Design]]`) are answered *only* from reels in that subcategory. The graph traversal walks a strict 4-tier topology (**Category -> Subcategory -> Concept -> Reel**), ensuring sibling branches never bleed into each other during RAG.

## Local Setup Instructions

You only need Docker Desktop and a configured `.env` file to run the complete stack.

### 1. Configure Environment
```bash
cp env.example .env
# Edit .env and replace the example DATABRICKS_DATABASE_URL and add your GEMINI_API_KEY
