# 🛡️ CIS Controls Compliance RAG

A **Retrieval-Augmented Generation (RAG)** application built for cybersecurity compliance auditing. It allows you to ask natural language questions about **CIS Controls v8.1** and get precise, sourced answers powered by a local LLM — no data ever leaves your machine.

![RAG Architecture](https://img.shields.io/badge/Architecture-Hybrid%20RAG-blue?style=for-the-badge)
![LLM](https://img.shields.io/badge/LLM-Ollama%20(Local)-green?style=for-the-badge)
![Vector DB](https://img.shields.io/badge/VectorDB-ChromaDB-orange?style=for-the-badge)
![Backend](https://img.shields.io/badge/Backend-FastAPI-teal?style=for-the-badge)

---

## 📌 What This Project Does

This project is a fully local, privacy-first compliance chatbot. You drop in a CIS Controls PDF, run a few scripts to process it, and then ask questions like:

> *"What safeguards are required for data encryption at rest?"*
> *"Which controls apply to privileged account management?"*

The system retrieves the most relevant safeguard chunks and passes them to a local LLM (via **Ollama**) to generate a concise, cited answer — complete with Control IDs, Safeguard IDs, and page references.

---

## ✅ What Has Been Built

### 🔍 Data Pipeline
| Script | Purpose |
|---|---|
| `scripts/extract_safeguards.py` | Parses the CIS Controls PDF (v8.1) using `pdfplumber`, extracts every safeguard with its Control ID, Safeguard ID, name, content, and page number |
| `scripts/extract_metadata.py` | Extracts a separate metadata index of all controls and safeguards |
| `scripts/chunk_safeguards.py` | Validates and prepares chunks for embedding |
| `scripts/create_vector_db.py` | Generates sentence embeddings (`BAAI/bge-small-en-v1.5`) and stores them in a persistent **ChromaDB** vector store |

### 🔎 Hybrid Retrieval System (`retrieval/`)
A multi-stage retrieval pipeline was implemented for high-accuracy results:

1. **Vector Retriever** — Semantic similarity search using `SentenceTransformer` embeddings in ChromaDB (top 20 results)
2. **BM25 Retriever** — Keyword-based sparse retrieval using `rank_bm25` (top 20 results)
3. **Reciprocal Rank Fusion (RRF)** — Merges and re-ranks results from both retrievers using the RRF algorithm
4. **Cross-Encoder Reranker** — Final reranking using `cross-encoder/ms-marco-MiniLM-L-6-v2` to select the top 3 most relevant chunks

### 🤖 LLM Integration
- Uses **Ollama** to run a local LLM (`llama3.2:1b` by default)
- System prompt configured as a strict compliance auditor via `config/prompts.yaml`
- LLM answers ONLY from provided context — no hallucination from general knowledge

### 🌐 REST API (`api/`)
- Built with **FastAPI**
- `GET /` — Health check
- `POST /chat` — Accepts a question, runs the full RAG pipeline, returns an answer with structured source citations (Control ID, Safeguard ID, page number)

### 🖥️ Frontend (`frontend/`)
- Vanilla HTML/CSS/JavaScript chat UI
- Real-time chat interface with a compliance auditor bot
- Displays answer and source references for every response
- Styled with Inter font and Font Awesome icons

---

## 🗂️ Project Structure

```
Compliance-RAG-System/
├── api/
│   └── main.py              # FastAPI app — /chat endpoint
├── config/
│   ├── prompt_loader.py     # Loads system prompt from YAML
│   └── prompts.yaml         # System prompt for the LLM
├── data/
│   ├── raw/                 # Place your CIS Controls PDF here (not in git)
│   └── processed/           # Extracted safeguards JSON (generated)
├── frontend/
│   ├── index.html           # Chat UI
│   ├── style.css            # Styles
│   └── app.js               # Frontend logic (API calls)
├── retrieval/
│   ├── vector_retriever.py  # ChromaDB semantic search
│   ├── bm25_retriever.py    # BM25 keyword search
│   ├── hybrid_retriever.py  # Combines vector + BM25 + RRF + reranker
│   ├── rrf.py               # Reciprocal Rank Fusion
│   └── reranker.py          # Cross-encoder reranker
├── scripts/
│   ├── extract_safeguards.py    # Step 1: Extract data from PDF
│   ├── extract_metadata.py      # Step 2: Extract metadata index
│   ├── create_vector_db.py      # Step 3: Build ChromaDB
│   └── ...                      # Validation & test scripts
├── chroma_db/               # Persistent vector DB (generated, not in git)
├── requirements.txt
└── .gitignore
```

---

## 🚀 How to Use This Project (Setup Guide)

### Prerequisites

- Python 3.10 or higher
- [Ollama](https://ollama.com/) installed and running
- The **CIS Controls v8.1 PDF** (you must obtain this from [CIS](https://www.cisecurity.org/controls))
- Git

---

### Step 1 — Clone the Repository

```bash
git clone https://github.com/Rishi52/Compliance-RAG-System.git
cd Compliance-RAG-System
```

---

### Step 2 — Create a Virtual Environment

```bash
python -m venv venv

# Activate on Windows
venv\Scripts\activate

# Activate on macOS/Linux
source venv/bin/activate
```

---

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```
---

### Step 4 — Install Ollama and Pull a Model

1. Download Ollama from [https://ollama.com/](https://ollama.com/) and install it.
2. Pull the default model:

```bash
ollama pull llama3.2:1b
```

3. Make sure Ollama is running (it starts automatically on most systems, or run `ollama serve`).

---

### Step 5 — Add the CIS Controls PDF

Place the CIS Controls PDF inside the `data/raw/` folder:

```
data/raw/CIS_Controls_Guide_v8.1.2_0325_v2.pdf
```

> ⚠️ The filename must match exactly, or update the `PDF_PATH` variable in `scripts/extract_safeguards.py`.

---

### Step 6 — Run the Data Pipeline

```bash
# Extract safeguards from the PDF
python scripts/extract_safeguards.py

# Build the ChromaDB vector database
python scripts/create_vector_db.py
```

You should see output like:
```
Extracted 153 safeguards
Stored 153 safeguards
```

---

### Step 7 — Start the API Server

```bash
uvicorn api.main:app --reload
```

The API will be available at: `http://localhost:8000`

---

### Step 8 — Open the Frontend

Open `frontend/index.html` in your browser directly (double-click it), or serve it with any static file server:

```bash
# Using Python's built-in server
python -m http.server 5500 --directory frontend
```

Then visit `http://localhost:5500` and start asking compliance questions!

---

## 🔄 Using a Different Local LLM Model

The application uses **Ollama** as its LLM backend, so switching models is very easy.

### Step 1 — Pull a different model

```bash
# Examples of models you can use:
ollama pull llama3.2:3b          # Larger, more capable Llama 3.2
ollama pull llama3.1:8b          # Llama 3.1 8B — best quality locally
ollama pull mistral:7b           # Mistral 7B — fast and capable
ollama pull gemma2:2b            # Google Gemma 2 2B — very lightweight
ollama pull phi3:mini            # Microsoft Phi-3 Mini — efficient
ollama pull deepseek-r1:7b       # DeepSeek reasoning model
```

To see all available models: [https://ollama.com/library](https://ollama.com/library)

### Step 2 — Update `api/main.py`

Open `api/main.py` and change the `model` parameter in the `ChatOllama` call:

```python
# Line 24-27 in api/main.py
llm = ChatOllama(
    model="llama3.2:1b",   # <-- Change this to your preferred model
    temperature=0
)
```

**For example, to use Mistral 7B:**
```python
llm = ChatOllama(
    model="mistral:7b",
    temperature=0
)
```

### Step 3 — Restart the server

```bash
uvicorn api.main:app --reload
```

That's it! The rest of the pipeline (retrieval, reranking, prompt) stays the same.

> **💡 Tips for choosing a model:**
> - Use `llama3.2:1b` or `gemma2:2b` on low-RAM machines (8GB RAM)
> - Use `llama3.1:8b` or `mistral:7b` for better answer quality (16GB+ RAM recommended)
> - Set `temperature=0` for deterministic compliance answers

---

## ⚙️ Configuration

| File | What to Configure |
|---|---|
| `api/main.py` | `model=` in `ChatOllama(...)` to switch LLM |
| `api/main.py` | `k=` in `retriever.search(...)` to change number of retrieved chunks |
| `config/prompts.yaml` | Edit the system prompt to change the auditor's tone/style |
| `retrieval/vector_retriever.py` | `embedding_model=` to change the embedding model |
| `retrieval/hybrid_retriever.py` | Tune `k` values in `vector.search()` and `bm25.search()` |
| `retrieval/reranker.py` | Change the cross-encoder model for reranking |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Ollama (any local model) |
| **Embeddings** | `BAAI/bge-small-en-v1.5` via SentenceTransformers |
| **Vector Store** | ChromaDB (persistent, local) |
| **Sparse Retrieval** | BM25 (`rank-bm25`) |
| **Fusion** | Reciprocal Rank Fusion (RRF) |
| **Reranking** | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| **PDF Parsing** | `pdfplumber` |
| **Backend API** | FastAPI + Uvicorn |
| **Frontend** | Vanilla HTML, CSS, JavaScript |

---

## 📄 License

This project is for educational purposes. The CIS Controls document is copyrighted by the Center for Internet Security — you must obtain it independently.
