# Deployment Guide — Enterprise Compliance AI Platform

## Architecture

| Layer | Service | URL |
|---|---|---|
| Frontend | Vercel | https://autonomous-compliance-audit-platfor.vercel.app |
| Backend | Render | https://autonomous-compliance-audit-platform.onrender.com |
| Database | Supabase PostgreSQL | — |
| Vector Store | ChromaDB (ephemeral on Render) | — |

---

## LLM Provider Configuration

The backend supports four LLM providers selected via the `LLM_PROVIDER` environment variable.

### Supported Providers

| Provider | Env var | Free tier | Best for |
|---|---|---|---|
| **Groq** (recommended) | `LLM_PROVIDER=groq` | ✅ Yes | Production on Render |
| OpenAI | `LLM_PROVIDER=openai` | ❌ Paid | Highest quality |
| Gemini | `LLM_PROVIDER=gemini` | ✅ Yes | Google ecosystem |
| Ollama | `LLM_PROVIDER=ollama` | ✅ Yes (local) | Local development only |

---

## Production Setup (Render + Groq)

### Step 1: Get a Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up for a free account
3. Navigate to **API Keys** → **Create API Key**
4. Copy the key (starts with `gsk_...`)

### Step 2: Set Render Environment Variables

In your Render backend service dashboard:

1. Go to **Environment** tab
2. Add these variables:

```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_YOUR_KEY_HERE
GROQ_MODEL=llama3-8b-8192
```

3. Click **Save Changes** — Render will auto-redeploy

### Step 3: Verify

- Check `/api/v1/health` → `"llm": "Groq API reachable — model: llama3-8b-8192"`
- Dashboard LLM status should show ✅ Healthy

---

## Local Development (Ollama)

### Prerequisites
- Ollama installed: https://ollama.ai
- Model pulled: `ollama pull llama3`

### Configuration

In your `backend/.env`:
```
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3
OLLAMA_BASE_URL=http://localhost:11434
```

Start Ollama: `ollama serve`

---

## Alternative: OpenAI

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

## Alternative: Google Gemini

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-1.5-flash
```

Get a free Gemini key at [aistudio.google.com](https://aistudio.google.com).

---

## ChromaDB Note

ChromaDB on Render uses a local filesystem (`./chroma_db`) which is **ephemeral** — it resets on every redeploy.

The platform handles this automatically:
- **When documents are uploaded:** Real document chunks are used for analysis
- **When ChromaDB is empty:** Built-in demo GDPR/Company Policy content is used as fallback

This ensures all features work immediately after deployment without requiring manual document uploads.

---

## Health Check Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/v1/health` | Full system health check |
| `GET /api/v1/health/live` | Liveness probe |

### Example Health Response

```json
{
  "database": "healthy",
  "chromadb": "healthy",
  "llm": "Groq API reachable — model: llama3-8b-8192",
  "google_drive": "not_configured",
  "notion": "not_configured",
  "backend": "healthy"
}
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Dashboard LLM: Error | `GROQ_API_KEY` not set | Add `GROQ_API_KEY` to Render env vars |
| "LLM provider unavailable" | Wrong provider config | Check `LLM_PROVIDER` value |
| "No policy documents found" | Won't happen (demo fallback) | Upload real PDFs for production content |
| Login fails | Auth misconfigured | Check `SECRET_KEY` and `DATABASE_URL` |
