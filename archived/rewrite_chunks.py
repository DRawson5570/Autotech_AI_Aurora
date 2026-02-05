#!/usr/bin/env python3
"""
Rewrite all text chunks from a ChromaDB collection using an LLM and output as a new file.

- Connects to ChromaDB (local path)
- Retrieves all chunks for a given collection (by name or ID)
- Uses OpenAI API (or local LLM endpoint) to rewrite each chunk
- Outputs rewritten text to a file, sorted by page if possible

Usage:
    python3 rewrite_chunks.py --collection <collection_id> --output <output_file> [--llm_api <url>] [--api_key <key>]

Example:
    python3 rewrite_chunks.py --collection ea2ce8c9-b304-4e0c-a485-5a28efd064b3 --output rewritten.txt
"""
import sys
import os
import argparse
import chromadb
import time
import json
from operator import itemgetter

# --- LLM API ---
def rewrite_text(text, llm_api=None, api_key=None):
    """Rewrite text using an LLM API (OpenAI-compatible or local)."""
    import requests
    prompt = (
        "Rewrite the following technical information in your own words, preserving all facts and details. "
        "Do not copy any phrases verbatim.\n\nText to rewrite:\n" + text
    )
    # Detect Ollama endpoint (if /api/chat or /api/ is in URL)
    url = llm_api or "https://api.openai.com/v1/chat/completions"
    is_ollama = url and ("ollama" in url or "/api/chat" in url or ":11434" in url)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if is_ollama:
        # Ollama chat API
        payload = {
            "model": "gpt-oss:20b",
            "messages": [
                {"role": "system", "content": "You are a technical writer."},
                {"role": "user", "content": prompt}
            ]
        }
        chat_url = url if "/api/chat" in url else url.rstrip("/") + "/api/chat"
    else:
        # OpenAI format
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a technical writer."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1024,
            "temperature": 0.4,
        }
        chat_url = url
    try:
        resp = requests.post(chat_url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        try:
            data = resp.json()
        except ValueError:
            # Some local endpoints or streaming responses send NDJSON / SSE with multiple JSON objects.
            # Try to recover by finding the last JSON object in the response text.
            text_body = resp.text.strip()
            json_obj = None
            for line in text_body.splitlines():
                s = line.strip()
                if s.startswith('{') and s.endswith('}'):
                    json_obj = s
            if json_obj:
                import json as _json
                data = _json.loads(json_obj)
            else:
                # Fallback: try extracting substring between first { and last }
                start = text_body.find('{')
                end = text_body.rfind('}')
                if start != -1 and end != -1 and end > start:
                    import json as _json
                    data = _json.loads(text_body[start:end+1])
                else:
                    raise
        # Extract the content from common response shapes
        if is_ollama:
            try:
                if isinstance(data, dict) and "message" in data and isinstance(data["message"], dict) and "content" in data["message"]:
                    return data["message"]["content"].strip()
                if isinstance(data, dict) and "choices" in data and data["choices"]:
                    c = data["choices"][0]
                    if isinstance(c, dict) and "message" in c and "content" in c["message"]:
                        return c["message"]["content"].strip()
                    if isinstance(c, dict) and "content" in c:
                        return c["content"].strip()
                if isinstance(data, dict) and "output" in data:
                    out = data["output"]
                    if isinstance(out, list):
                        texts = []
                        for item in out:
                            if isinstance(item, dict) and "content" in item:
                                texts.append(item["content"])
                        if texts:
                            return "\n".join(texts).strip()
                return resp.text.strip()
            except Exception:
                print(f"[ERROR] Failed to parse Ollama response; status={resp.status_code}")
                return "[REWRITE ERROR] " + text[:200]
        else:
            try:
                return data["choices"][0]["message"]["content"].strip()
            except Exception:
                print(f"[ERROR] Failed to parse OpenAI response; status={resp.status_code}")
                return "[REWRITE ERROR] " + text[:200]
    except Exception as e:
        print(f"[ERROR] LLM call failed: {e}")
        return "[REWRITE ERROR] " + text[:200]

# --- Main utility ---
def main():
    parser = argparse.ArgumentParser(description="Rewrite ChromaDB collection chunks with LLM.")
    parser.add_argument('--collection', required=True, help='ChromaDB collection name or ID')
    parser.add_argument('--output', required=True, help='Output file for rewritten text')
    parser.add_argument('--llm_api', default=None, help='OpenAI-compatible API endpoint (default: OpenAI)')
    parser.add_argument('--api_key', default=None, help='API key for LLM (if needed)')
    parser.add_argument('--db_path', default='/prod/autotech_ai/backend/data/vector_db', help='ChromaDB path')
    args = parser.parse_args()

    client = chromadb.PersistentClient(path=args.db_path)
    coll = client.get_collection(args.collection)
    print(f"Loaded collection: {args.collection}")
    # Get all chunks (may need to page if huge)
    all_chunks = []
    offset = 0
    batch = 100
    while True:
        results = coll.get(limit=batch, offset=offset, include=["documents", "metadatas"])
        docs = results["documents"]
        metas = results["metadatas"]
        if not docs:
            break
        for doc, meta in zip(docs, metas):
            all_chunks.append({"text": doc, "meta": meta})
        offset += batch
        if len(docs) < batch:
            break
    print(f"Found {len(all_chunks)} chunks.")
    # Sort by file, then page, then start_index if available
    def sort_key(chunk):
        m = chunk["meta"]
        return (
            m.get("file_id", ""),
            int(m.get("page", 0)) if m.get("page") else 0,
            int(m.get("start_index", 0)) if m.get("start_index") else 0
        )
    all_chunks.sort(key=sort_key)
    # Rewrite and write to file
    with open(args.output, "w", encoding="utf-8") as f:
        for i, chunk in enumerate(all_chunks):
            orig = chunk["text"]
            meta = chunk["meta"]
            print(f"Rewriting chunk {i+1}/{len(all_chunks)} (page {meta.get('page', '?')})...")
            rewritten = rewrite_text(orig, llm_api=args.llm_api, api_key=args.api_key)
            f.write(f"\n\n=== [Page {meta.get('page', '?')}] ===\n")
            f.write(rewritten)
            f.flush()
            time.sleep(1)  # avoid rate limits
    print(f"Done. Output written to {args.output}")

if __name__ == "__main__":
    main()
