# Document Management — backend

# Document Management Backend

The Document Management (DMS) module provides file ingestion, OCR processing, and document storage for the debate platform. Uploaded documents can be linked to debates and used as a RAG (Retrieval-Augmented Generation) context source.

## Architecture overview

```
┌─────────────────────────┐    ┌───────────────────────────────┐
│   Debate API Router     │    │   DMS API Router              │
│   /api/v1/debate        │    │   /api/v1/dms                 │
│                         │    │                               │
│   PUT /{id}/documents   │    │   POST /documents             │
│   GET /{id} (RAG info)  │    │   GET  /ocr-status            │
└─────────┬───────────────┘    └───────────┬───────────────────┘
           │                               │
           │    ┌──────────────────┐       │
           └────│    DMS Service    │←──────┘
                │  (DMS class)     │
                │                  │
                │ ┌──────────────┐ │
                │ │Document      │ │
                │ │Processor     │ │
                │ │(OCR, text    │ │
                │ │ extraction)  │ │
                │ └──────────────┘ │
                │ ┌──────────────┐ │
                │ │Chroma        │ │
                │ │vector store  │ │
                │ └──────────────┘ │
                │ ┌──────────────┐ │
                │ │SQLite (docs, │ │
                │ │debate links)│ │
                │ └──────────────┘ │
                └──────────────────┘
```

- **DMS API Router** handles file uploads and OCR status queries.
- **Debate API Router** manages the link between debates and documents, and exposes RAG metadata in debate responses.
- **DMS Service** (`backend.services.dms.service.DMS`) orchestrates processing, storage, and retrieval.
- **DocumentProcessor** (`backend.services.dms.document_processor.DocumentProcessor`) performs text extraction with optional OCR.

## API endpoints

### Document upload

```
POST /api/v1/dms/documents
```

Accepts one or more files via multipart/form-data. Each file is processed synchronously. Response contains a `document_id` and processing status.

**Example (Python client):**
```python
import httpx

files = [("file", ("report.png", open("report.png", "rb"), "image/png"))]
r = httpx.post("http://localhost:8000/api/v1/dms/documents", files=files)
r.json()  # → {"status": "ok", "document_id": "...", "chunk_count": 3}
```

**Error cases:**
- Image upload when `ocr_enabled=False` returns 400 with explanation.
- Unreadable or empty files return 422.

### OCR engine status

```
GET /api/v1/dms/ocr-status
```

Returns whether an OCR engine is available and which one is used.

```json
{
  "available": true,
  "engine": "paddleocr"
}
```

If neither `paddleocr` nor `pytesseract` can be imported, `available` is `false` and `engine` is `null`.

### Link documents to a debate

```
PUT /api/v1/debate/{debate_id}/documents
```

Assign a list of document IDs to a debate and optionally enable automatic context retrieval.

```json
{
  "document_ids": ["doc-abc", "doc-def"],
  "rag_auto_retrieve": true
}
```

Returns 200 with the updated assignment. Sending an empty list clears all document links.

### Debate status (RAG fields)

```
GET /api/v1/debate/{debate_id}
```

Response includes three RAG-related fields:

| Field                 | Type    | Description                                    |
|-----------------------|---------|------------------------------------------------|
| `rag_enabled`         | bool    | True if documents or auto-retrieve are set     |
| `rag_document_count`  | int     | Number of linked documents                     |
| `rag_context_preview` | string  | Preview snippet of concatenated document text  |

## Core components

### DocumentProcessor

Located in `backend.services.dms.document_processor`. Its primary method `process_file(path)` returns a dict with extracted `text` and a boolean `ocr_used`.

- If the file is an image (PNG etc.) and `ocr_enabled` is `False`, a `ValueError` is raised.
- If the file is an image and `ocr_enabled` is `True`, it attempts OCR via `paddleocr`.
- When `paddleocr` is not installed and OCR is enabled, `ocr_used` is set to `False` (graceful fallback).
- Non-image files are read as text directly, unaffected by the `ocr_enabled` toggle.

**Instantiation:**
```python
from backend.services.dms.document_processor import DocumentProcessor

processor = DocumentProcessor(config={
    "ocr_enabled": True,
    "ocr_device": "cpu"
})
result = await processor.process_file("/path/to/scan.png")
# result → {"text": "...", "ocr_used": True, ...}
```

### DMS service class

`backend.services.dms.service.DMS` ties together document processing, metadata storage (SQLite), and vector embedding (Chroma). It receives the current config and instantiates a `DocumentProcessor`.

```python
dms = DMS(
    db_path=":memory:",
    chroma_path="/tmp/chroma",
    config=config
)
```

The `document_processor` attribute uses the same config object, so changes are reflected immediately.

### Configuration

`backend.services.dms.config` provides:

| Constant / Function       | Purpose                                |
|---------------------------|----------------------------------------|
| `DEFAULT_DMS_CONFIG`      | Default settings as a dict             |
| `load_dms_config(path)`   | Load from YAML, fall back to defaults  |

**Default values:**
```python
DEFAULT_DMS_CONFIG = {
    "ocr_enabled": True,
    "ocr_device": "cpu"
}
```

The `load_dms_config` function attempts to read a YAML file. If the file is missing or fails to parse, it returns a copy of `DEFAULT_DMS_CONFIG`.

## RAG integration

### Request schema (DebateRequest)

The `DebateRequest` model (used in `POST /api/v1/debate`) accepts two optional fields:

```json
{
  "document_ids": ["doc-1"],
  "rag_auto_retrieve": true
}
```

Both default to `[]` and `False` respectively.

### RAG info extraction

The internal helpers `_extract_rag_info()` and `_build_rag_preview()` (located in the debate router) derive the RAG state from a debate record:

- `rag_enabled` is `True` when either `document_ids` is non-empty or `rag_auto_retrieve` is `True`.
- `rag_document_count` is the length of `document_ids`.
- `rag_context_preview` is built by loading the stored document texts and concatenating the first few characters.

Because `_extract_rag_info` operates on the stored debate record, any updates via `PUT /debate/{id}/documents` become visible on subsequent `GET` requests.

## OCR integration details

| Scenario                                        | Behaviour                                                                 |
|-------------------------------------------------|---------------------------------------------------------------------------|
| `ocr_enabled=True`, `paddleocr` importable     | Image files are processed with PaddleOCR. Package is loaded on first use. |
| `ocr_enabled=True`, `paddleocr` not available  | Image files are skipped; `ocr_used=False`. No error is raised.            |
| `ocr_enabled=False`, image file                | `ValueError("requires OCR but ocr_enabled is false")`.                    |
| `ocr_enabled=False`, text file                 | Processed normally as plain text.                                         |

The engine detection (`GET /dms/ocr-status`) checks for `paddleocr` and `pytesseract` in `sys.modules`. This allows the status to change at runtime if new engines are installed.

## Error handling

- **Missing `paddleocr`:** graceful fallback for images, no crash.
- **OCR disabled with image:** immediate `ValueError` from `DocumentProcessor.process_file`.
- **Non-existent debate:** `PUT /debate/{id}/documents` returns 404.
- **Empty document list:** clearing assignments is allowed and resets RAG state.
- **API-level validation:** FastAPI validates request bodies; invalid types produce 422.

## Testing strategy

The test suite (see `tests/backend/test_dms_ocr.py` and `tests/backend/test_rag_integration.py`) covers:

- OCR endpoint with and without engine present (via `sys.modules` patching).
- DocumentProcessor with mocked `paddleocr` to verify OCR output.
- Real API uploads of images and text files.
- Config loading and fallback.
- RAG field defaults, assignment updates, and response consistency.
- Helper functions `_make_png_file`, `_make_text_file`, and `_upload_doc` simplify test setup.