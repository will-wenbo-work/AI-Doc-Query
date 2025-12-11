# RAG Frontend (PDF Chat)

This is a minimal frontend that allows selecting and uploading a PDF, then asking questions about it via a chat UI.

Quick start

1. Make sure your backend is running and exposes the expected endpoints:

- `POST /upload_pdf` — accepts a multipart/form-data `file` field and should return JSON with at least a `doc_id` or similar identifier. Example response: `{ "doc_id": "abc123" }`.
- `POST /chat` — accepts JSON `{ "question": "...", "doc_id": "..." }` and returns JSON `{ "answer": "..." }`.

2. Serve the `frontend/` folder (e.g., open `frontend/index.html` in a browser, or run a simple static server):

```bash
# from repo root
python3 -m http.server --directory frontend 8001
# then open http://localhost:8001 in your browser
```

3. Optionally change the backend URL by adding a small script before `app.js` in `index.html`:

```html
<script>window.BACKEND_URL = 'http://localhost:8000'</script>
<script src="app.js"></script>
```

Notes & next steps

- Frontend is intentionally simple — it does not perform any local PDF parsing. The backend should implement the RAG pipeline: extract text, create embeddings, store them, and answer questions using retrieval + LLM.
- If you want streaming responses from the backend, adjust `app.js` to read a text/streaming response and append partial chunks to the chat UI.

If you want, I can implement matching backend endpoints in `backend/app.py` next.
