# AutoLoadGen

**AutoLoadGen** is an automated **HAR-to-JMeter** test plan generator. It takes recorded HTTP Archive (`.har`) traffic, detects producer–consumer data dependencies across API requests, lets you inspect or refine the resulting dependency graph in a visual editor, and exports a correlated, ready-to-run Apache JMeter (`.jmx`) load test plan.

## Core Features

* **Automated Dependency Correlation**: Detects dynamic values flowing from earlier responses into later requests across **URL path segments**, **headers**, **query parameters**, **cookies**, **URL-encoded form bodies (`bodyue`)**, and **JSON bodies (`bodyjson`)**.

* **Four Matching Strategies**:

  * **Hybrid (`LCS + Embedding`)** *(default)*: Fast Longest Common Substring (LCS) matching with semantic embedding fallback (`all-MiniLM-L6-v2`).

  * **LCS**: Pure lexical substring similarity—fastest with no model calls.

  * **Embedding**: Semantic vector similarity using `sentence-transformers/all-MiniLM-L6-v2`.

  * **LLM**: Semantic verification via **OpenAI** or **Ollama** endpoints using configurable prompt templates.

* **Interactive Dependency Graph Editor**: Visualize endpoints and correlations as an interactive SVG graph, filter by node or edge type, add/edit/delete edges, bind **CSV data sources**, and import/export `graph.json`.

* **JMeter Test Plan Generation**: Builds `.jmx` XML with `HTTPSamplerProxy` nodes, `JSONPostProcessor` extractors, cookie `RegexExtractor` elements, Groovy preprocessors for nested JSON body updates, `CSVDataSet` elements, and `UltimateThreadGroup` workload schedules.

## Common Applications

* **Performance & Load Testing**: Convert browser or API client HAR captures into parameterized JMeter scripts without manual regex/JSONPath correlation.

* **API Regression & CI/CD Pipelines**: Use the REST API (`POST /graphs/build` and `POST /jmx/build`) to generate or refresh `.jmx` load scripts automatically.

* **Dynamic Token & ID Propagation**: Automatically correlate session tokens, cookies, CSRF values, and resource IDs across multi-step user journeys.

## Technical Architecture

### Project Structure

The project uses Python 3 namespace packages (no `__init__.py` files) with `requirements.txt` at the root and `run.py` inside `app/`:

```
.
├── requirements.txt                # Project Python dependencies
└── app/
    ├── main.py                     # FastAPI app, REST endpoints, and static UI serving
    ├── run.py                      # Application entry point (Uvicorn server)
    ├── config/
    │   ├── config.py               # Runtime config loader/saver
    │   └── config.json             # Persisted LLM & matcher configuration
    ├── models/
    │   ├── har_model.py            # HAR data structures (Entry, Request, Response, Header, Cookie)
    │   └── response_model.py       # Flattened response models (AtomicObject, StructuredObject)
    ├── graph/
    │   ├── graph.py                # DependencyGraph, MyNode, CSVNode, Edge models
    │   └── graph_ops.py            # Graph inspection and CRUD operations on edges
    ├── analysis/
    │   ├── response_analyzer.py    # Recursive JSON/header flattening into atomic fields
    │   ├── schema_generator.py     # JSON schema inference
    │   ├── schema_client.py        # Canonical JSON-schema fingerprinting & LRU cache
    │   ├── detectors.py            # URL, header, query, cookie, and body dependency detectors
    │   ├── validator.py            # Candidate dependency scoring (LCS / Embedding / LLM)
    │   └── extractor.py            # Orchestrates HAR analysis and dependency graph construction
    ├── matchers/
    │   ├── lcs_matcher.py          # Normalized Longest Common Substring similarity
    │   ├── embedding_matcher.py    # SentenceTransformer (all-MiniLM-L6-v2) similarity matcher
    │   ├── lcs_embedding_matcher.py# Hybrid LCS-first, embedding-fallback matcher
    │   ├── llm_matcher.py          # OpenAI / Ollama client and response parser
    │   └── prompts.py              # Versioned LLM prompt templates
    ├── jmeter/
    │   ├── jmx_base.py             # Base JMeter test plan builder (skips static assets)
    │   ├── jmx_correlate.py        # Injects extractors, variable references, and CSV datasets
    │   └── jmx_load.py             # Workload parser and UltimateThreadGroup builder
    └── static/
        ├── index.html              # Single-page 3-step Web UI
        ├── app.js                  # Frontend logic, SVG graph renderer, API client
        └── styles.css              # Light/dark glassmorphic styling

```

### Processing Pipeline

1. **HAR Parsing (`models/har_model.py`)**: Parses `.har` JSON entries into typed `Request` and `Response` objects.

2. **Response Flattening & Schema Fingerprinting (`analysis/response_analyzer.py`, `analysis/schema_client.py`)**: Recursively decomposes JSON responses and `Set-Cookie` headers into `AtomicObject` and `StructuredObject` nodes with canonical JSON schema fingerprints.

3. **Dependency Detection (`analysis/detectors.py`, `analysis/validator.py`)**: Compares each consumer request against preceding producer responses across URLs, headers, query parameters, cookies, and request bodies, validating matches via LCS, embeddings, or LLM.

4. **JMeter Correlation & Load Modeling (`jmeter/jmx_base.py`, `jmeter/jmx_correlate.py`, `jmeter/jmx_load.py`)**: Strips static assets (`.js`, `.css`, images, fonts), inserts `JSONPostProcessor` / `RegexExtractor` / `CSVDataSet` elements, replaces static consumer values with `${var}` references, and applies `UltimateThreadGroup` schedules.

## Running from Scratch

### Prerequisites

* **Python 3.10+** (uses PEP 604 union types `X | Y`, `from __future__ import annotations`, and namespace packages)

* **pip** (comes with Python)

* *(Optional)* **Ollama** or an **OpenAI-compatible API key** if using the **LLM** matching mode

* *(Optional)* **Apache JMeter** (with the `UltimateThreadGroup` plugin if using custom load profiles) to execute exported `.jmx` files

### 1. Create a Virtual Environment & Install Dependencies

Open a terminal in the **project root directory** (where `requirements.txt` and the `app/` folder are located) and run the commands for your OS:

#### Windows (PowerShell)

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt

```

*(If PowerShell blocks script execution, run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once, or use Command Prompt with `.\.venv\Scripts\activate.bat`.)*

#### macOS

```
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt

```

#### Linux

```
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt

```

> **Note on Embedding & LLM Modes**:
>
> * **Embedding / Hybrid modes** download `sentence-transformers/all-MiniLM-L6-v2` into `app/cache/all-MiniLM-L6-v2` on first use if not already present.
>
> * **LLM mode** reads settings from `app/config/config.json` or updates made via the UI **Config** modal (`llm_provider`, `llm_endpoint`, `llm_apikey`, `model`, `timeout`, `fallback_to_lcs`, `cache_enabled`).

### 2. Start the Server

Run the application from the **project root directory** (so Python resolves the `app` package):

#### Windows

```
python -m app.run

```

#### macOS / Linux

```
python3 -m app.run

```

The server starts on `http://127.0.0.1:8000`:

* **Web UI**: `http://127.0.0.1:8000/`

* **Interactive Swagger API Docs**: `http://127.0.0.1:8000/docs`

## Web UI & API Reference

The Web UI (`app/static/index.html`) guides you through a **3-step workflow** backed directly by the FastAPI endpoints:

### Step-by-Step UI Workflow

1. **Step 1 — Upload & Config**:

   * Drag and drop a `.har` file and select a dependency matching mode (**Hybrid LCS + Embedding**, **LCS**, **Embedding**, or **LLM**).

   * Define one or more load profile rows (`threads`, `delay`, `startup`, `hold`, `shutdown`) for `UltimateThreadGroup`.

   * Click **Build dependency graph →** to inspect/edit dependencies, or **Quick JMX** to skip directly to `.jmx` download.

   * Use the top-bar **⚙ Config** button to view or update runtime LLM settings.

2. **Step 2 — Dependency Graph**:

   * Explore the interactive SVG graph (nodes = HTTP endpoints, edges = data dependencies).

   * Filter nodes by URL/method, filter edges by type (`url`, `header`, `queryparam`, `cookie`, `bodyue`, `bodyjson`), zoom/fit/auto-layout, or export the graph as **PNG** or **`graph.json`**.

   * Use the right-hand sidebar tabs (**Details**, **Edges**, **Add edge**) to inspect, edit, delete, or manually add endpoint-to-endpoint or CSV-backed dependencies.

3. **Step 3 — Confirm & JMX**:

   * Review the confirmed graph summary, click **Build JMX script**, preview the generated XML, and download the `.jmx` file.

### REST API Endpoints

| Method & Path | UI Counterpart | Description | 
| ----- | ----- | ----- | 
| `GET /health` | Top-bar health badge | Returns `{"status": "ok"}` to verify the service is running. | 
| `GET /config` | Top-bar **⚙ Config** modal (load) | Returns the active runtime configuration dictionary. | 
| `PUT /config` | Top-bar **⚙ Config** modal (save) | Updates `llm_provider`, `llm_endpoint`, `llm_apikey`, `model`, `timeout`, `fallback_to_lcs`, and `cache_enabled`, persisting to `app/config/config.json`. | 
| `POST /graphs/build` | Step 1 **Build dependency graph** | Accepts multipart `har` file plus `use_llm`, `use_embedding`, and `use_lcs_embedding` flags; returns node/edge counts, matching `mode`, and `graph` JSON. | 
| `POST /graphs/describe` | Graph inspection | Accepts `{"graph": ...}` and returns a human-readable text summary with node and edge counts. | 
| `POST /graphs/edges/list` | Step 2 **Edges** tab / type filter | Lists edges in `graph`, optionally filtered by `to_idx` and `type`. | 
| `POST /graphs/edges/add` | Step 2 **Add edge** tab | Adds an endpoint-to-endpoint or CSV (`file.csv:column`) dependency edge and returns the updated graph. | 
| `POST /graphs/edges/edit` | Step 2 **Edit dependency** modal | Modifies an existing edge's `type`, `key`, `value`, `producer_field`, `consumer_field`, or `common_value`. | 
| `POST /graphs/edges/delete` | Step 2 **Edges** tab delete button | Removes an edge by `id` and returns the updated graph. | 
| `POST /jmx/build` | Step 1 **Quick JMX** & Step 3 **Build JMX script** | Accepts multipart `har` file, optional `graph` file (or `auto_graph=true`), matching mode flags, and `workload` strings (`threads=...,delay=...,startup=...,hold=...,shutdown=...`); returns the correlated `.jmx` XML file. | 
