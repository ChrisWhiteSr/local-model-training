from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Any, Iterable, Tuple

import fitz  # PyMuPDF

from .clients.lmstudio import LMStudioEmbeddings
from .clients.openai_vlm import OpenAIVLM
from .settings import get_settings
from .vector_store import ChromaStore


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _read_file_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def _checksum_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    text = text.strip()
    if not text:
        return []

    # Try sentence-aware chunking
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0
    for sent in sentences:
        sent_len = len(sent)
        if current_len + sent_len + 1 <= chunk_size:
            current.append(sent)
            current_len += sent_len + 1
        else:
            if current:
                chunks.append(" ".join(current).strip())
            # start new chunk, carry some overlap from previous
            if chunks and overlap > 0:
                carry = chunks[-1][-overlap:]
                current = [carry, sent]
                current_len = len(carry) + 1 + sent_len
            else:
                current = [sent]
                current_len = sent_len
    if current:
        chunks.append(" ".join(current).strip())

    # Fallback if no sentence splitting worked
    if not chunks:
        for i in range(0, len(text), chunk_size - overlap):
            chunks.append(text[i : i + chunk_size])
    return [c for c in chunks if c]


@dataclass
class IngestResult:
    files_processed: int
    pages_processed: int
    chunks_upserted: int
    errors: List[Dict[str, Any]]


class Ingestor:
    def __init__(self, store: ChromaStore, embedder: LMStudioEmbeddings, index_path: str = os.path.join("data", "ingest_index.json")):
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        self.store = store
        self.embedder = embedder
        self.index_path = index_path
        self._index: Dict[str, str] = self._load_index()
        s = get_settings()
        self._vlm = OpenAIVLM(api_key=s.OPENAI_API_KEY, model=s.VLM_MODEL_ID) if s.VLM_PROVIDER == "openai" else None

    def _load_index(self) -> Dict[str, str]:
        if os.path.exists(self.index_path):
            try:
                with open(self.index_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_index(self) -> None:
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    async def ingest_paths(self, paths: List[str] | None = None) -> IngestResult:
        settings = get_settings()
        base_dir = settings.PDF_SOURCE_DIR
        errors: List[Dict[str, Any]] = []
        files_processed = 0
        pages_processed = 0
        chunks_upserted = 0

        # Resolve target files
        target_files: List[str] = []
        if paths:
            for p in paths:
                abs_path = p if os.path.isabs(p) else os.path.join(base_dir, p)
                if os.path.isfile(abs_path) and abs_path.lower().endswith(".pdf"):
                    target_files.append(abs_path)
        else:
            for root, _, files in os.walk(base_dir):
                for fn in files:
                    if fn.lower().endswith(".pdf"):
                        target_files.append(os.path.join(root, fn))

        for file_path in target_files:
            try:
                file_bytes = _read_file_bytes(file_path)
                checksum = _checksum_bytes(file_bytes)
                if self._index.get(file_path) == checksum:
                    continue  # unchanged

                with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                    per_page_chunks: List[str] = []
                    per_page_meta: List[Dict[str, Any]] = []
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        text = page.get_text("text") or ""
                        text = text.strip()
                        if not text:
                            # Use VLM OCR when text layer missing
                            vlm_text = ""
                            s = get_settings()
                            if self._vlm and s.OCR_VLM_ENABLED:
                                # Render page to PNG for VLM OCR (2x scale to improve small fonts)
                                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                                image_bytes = pix.tobytes("png")
                                try:
                                    vlm_text = await self._vlm.ocr_image(image_bytes)
                                except Exception:
                                    vlm_text = ""
                            text = (vlm_text or "").strip()
                            if not text:
                                # Skip pages that cannot be extracted
                                continue
                        chunks = _chunk_text(text)
                        for i, chunk in enumerate(chunks):
                            per_page_chunks.append(chunk)
                            per_page_meta.append(
                                {
                                    "source_file": os.path.relpath(file_path, base_dir),
                                    "page_number": page_num + 1,
                                    "chunk_index": i,
                                    "doc_title": doc.metadata.get("title") or os.path.basename(file_path),
                                    "checksum": checksum,
                                    "has_text_layer": bool(page.get_text("text")),
                                    "vlm_correction_applied": (not bool(page.get_text("text"))) and bool(text),
                                    "vlm_provider": "openai" if ((not bool(page.get_text("text"))) and bool(text)) else None,
                                }
                            )

                    if per_page_chunks:
                        embeddings = await self.embedder.embed(per_page_chunks)
                        ids = [
                            f"{per_page_meta[i]['source_file']}#p{per_page_meta[i]['page_number']}#c{per_page_meta[i]['chunk_index']}"
                            for i in range(len(per_page_chunks))
                        ]
                        self.store.upsert(ids=ids, documents=per_page_chunks, metadatas=per_page_meta, embeddings=embeddings)

                        chunks_upserted += len(per_page_chunks)
                        pages_processed += len(doc)
                        files_processed += 1
                        # Update index only after successful upsert
                        self._index[file_path] = checksum
                        self._save_index()
            except Exception as e:
                errors.append({"file": file_path, "error": str(e)})

        return IngestResult(
            files_processed=files_processed, pages_processed=pages_processed, chunks_upserted=chunks_upserted, errors=errors
        )
