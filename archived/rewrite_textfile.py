#!/usr/bin/env python3
"""
Rewrite a plain text file in chunks using an LLM and output the rewritten text.

- Reads a text file
- Splits into overlapping chunks (default: 1000 chars, 200 overlap)
- Rewrites each chunk using an LLM (OpenAI or local endpoint)
- Outputs rewritten text to a new file

Usage:
    python3 rewrite_textfile.py --input input.txt --output rewritten.txt [--llm_api <url>] [--api_key <key>]
"""
import argparse
import time
import requests
import json
import re
import traceback

# Path for per-chunk LLM debug logs (set in main)
LLM_DEBUG_PATH = None

def chunk_text(text, chunk_size=1000, overlap=200):
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks

def _parse_llm_response(resp, is_ollama=False):
    """Parse streamed or batched JSON responses from local LLMs (like Ollama).

    This function will attempt to parse all JSON objects in the response body (NDJSON/streaming) and
    reconstruct the assistant output by concatenating 'message.content', 'message.thinking', 'delta.content',
    'delta.thinking', or other available chunks in order.

    Returns (assembled_text_or_None, parsed_json_or_None, raw_text)
    """
    raw = resp.text or ""

    parts = []

    def _append(assembled, new):
        if not new:
            return assembled
        # ensure sensible spacing unless punctuation or whitespace suggests otherwise
        if not assembled:
            return new
        # If previous fragment ends with whitespace or new starts with whitespace, just concatenate
        if assembled[-1].isspace() or new[0].isspace():
            return assembled + new
        # If both sides are alphabetic (mid-word split from streaming), join without space
        if assembled[-1].isalpha() and new[0].isalpha():
            return assembled + new
        # If new starts with punctuation, append directly
        if new and new[0] in ',.:;?!)%]':
            return assembled + new
        # Otherwise separate with a single space
        return assembled + ' ' + new

    # Process response line-by-line to better handle NDJSON / streaming outputs
    parsed_any = None
    for line in raw.splitlines():
        l = line.strip()
        if not l:
            continue
        # strip pfx like 'data:' or 'event:'
        if l.startswith('data:'):
            l = l[len('data:'):].strip()
        if not l:
            continue
        jobj = None
        try:
            jobj = json.loads(l)
            parsed_any = jobj
        except Exception:
            # Try to recover JSON-like substring within the line
            m = re.search(r"(\{[\s\S]*\})", l)
            if m:
                try:
                    jobj = json.loads(m.group(1))
                    parsed_any = jobj
                except Exception:
                    jobj = None
        if jobj is None:
            # Fallback: extract 'content' fields with a regex (ignore 'thinking' fragments)
            m2 = re.search(r'"content"\s*:\s*"([\s\S]*?)"', l)
            if m2:
                try:
                    val = json.loads('"' + m2.group(1).replace('"', '\\"') + '"')
                except Exception:
                    val = m2.group(1)
                parts.append(val)
            continue
        # Extract known fields from jobj
        if isinstance(jobj, dict):
            if 'message' in jobj and isinstance(jobj['message'], dict):
                msg = jobj['message']
                # ignore 'thinking' internal fragments; use 'content' when present
                if 'content' in msg and msg.get('content'):
                    parts.append(msg.get('content'))
                continue
            if 'choices' in jobj and isinstance(jobj['choices'], list):
                for c in jobj['choices']:
                    if isinstance(c, dict):
                        if 'delta' in c and isinstance(c['delta'], dict):
                            d = c['delta']
                            # prefer delta.content; ignore delta.thinking
                            if 'content' in d and d.get('content'):
                                parts.append(d.get('content'))
                        if 'message' in c and isinstance(c['message'], dict):
                            m2 = c['message']
                            # prefer message.content; ignore message.thinking
                            if 'content' in m2 and m2.get('content'):
                                parts.append(m2.get('content'))
                        if 'content' in c and c.get('content'):
                            parts.append(c.get('content'))
                continue
            if 'output' in jobj and isinstance(jobj['output'], list):
                for item in jobj['output']:
                    if isinstance(item, dict):
                        if 'content' in item and item.get('content'):
                            parts.append(item.get('content'))
                        elif 'text' in item and item.get('text'):
                            parts.append(item.get('text'))
                continue
            if 'content' in jobj and jobj.get('content'):
                parts.append(jobj.get('content'))
                continue
            if 'text' in jobj and jobj.get('text'):
                parts.append(jobj.get('text'))
                continue

    # Assemble parts with smart spacing
    assembled = ''
    for p in parts:
        if not isinstance(p, str):
            try:
                p = str(p)
            except Exception:
                continue
        assembled = _append(assembled, p)

    # Post-process assembled text to fix spacing/punctuation artifacts
    def _post_process(s: str) -> str:
        s = s or ''
        # normalize unicode quotes/dashes to ASCII
        s = s.replace('\u2019', "'").replace('\u2018', "'")
        s = s.replace('\u2013', '-').replace('\u2014', '-').replace('\u2010', '-')
        # collapse multiple whitespace
        s = re.sub(r'\s+', ' ', s)
        # remove space before punctuation
        s = re.sub(r"\s+([,.:;?!)%\]])", r"\1", s)
        # remove space after opening paren/bracket
        s = re.sub(r"([\(\[\{])\s+", r"\1", s)
        # remove stray spaces around apostrophes and fix common contractions (e.g., it 's -> it's)
        s = re.sub(r"\b(\w+)\s+'\s+(\w+)\b", r"\1'\2", s)
        s = re.sub(r"\s+'s\b", "'s", s)
        s = re.sub(r"\s+n't\b", "n't", s)
        s = re.sub(r"\s+'re\b", "'re", s)
        s = re.sub(r"\s+'ve\b", "'ve", s)
        s = re.sub(r"\s+'ll\b", "'ll", s)
        s = re.sub(r"\s+'d\b", "'d", s)
        s = re.sub(r"\s+'m\b", "'m", s)
        # fix spaced hyphens: 'strategy -based' -> 'strategy-based'
        s = re.sub(r"\s*-\s*", "-", s)
        # Insert a space when a lowercase letter is immediately followed by uppercase (e.g., 'VehicleService' -> 'Vehicle Service')
        s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)
        # normalize common curly apostrophes and contractions (handle both straight and curly quotes)
        # Merge spaced contractions like "hasn 't" -> "hasn't" and "it 's" -> "it's"
        s = re.sub(r"\b([A-Za-z]+)\s+'(t|s|re|ve|ll|d|m)\b", lambda m: m.group(1) + "'" + m.group(2), s)
        s = re.sub(r"\s+[’']s\b", "'s", s)
        s = re.sub(r"\s+n[’']t\b", "n't", s)
        s = re.sub(r"\s+[’']re\b", "'re", s)
        s = re.sub(r"\s+[’']ve\b", "'ve", s)
        s = re.sub(r"\s+[’']ll\b", "'ll", s)
        s = re.sub(r"\s+[’']d\b", "'d", s)
        s = re.sub(r"\s+[’']m\b", "'m", s)
        # strip leading/trailing spaces
        return s.strip()

    if assembled:
        cleaned = _post_process(assembled.strip())
        return (cleaned, parsed_any, raw)

    # Heuristic fallback: try to extract a large content string from raw
    m = re.search(r'"content"\s*:\s*"([\s\S]{20,})"', raw)
    if m:
        try:
            extracted = m.group(1)
            content = json.loads('"' + extracted.replace('"', '\\"') + '"')
            return (content, parsed_any, raw)
        except Exception:
            return (m.group(1), parsed_any, raw)

    return (None, parsed_any, raw)


def rewrite_text(text, llm_api=None, api_key=None):
    prompt = (
        "Rewrite the following technical information in your own words, preserving all facts and details. "
        "Do not copy any phrases verbatim.\n\nText to rewrite:\n" + text
    )
    url = llm_api or "https://api.openai.com/v1/chat/completions"
    is_ollama = url and ("ollama" in url or "/api/chat" in url or ":11434" in url)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    # Stronger system and user instructions to force clean output
    system_msg = (
        "You are a professional technical writer. Return ONLY the rewritten text — no commentary, no headings, "
        "no meta text, and no lists unless explicitly asked. Preserve all facts and details; do NOT invent new facts. "
        "If the provided input is truncated, rewrite up to the provided end and do not make assumptions. Use fluent, "
        "well-formed paragraphs and normal punctuation."
    )
    user_msg = (
        "Rewrite the following technical information in your own words, preserving all facts and details. "
        "Do not copy phrases verbatim. Output only the rewritten text.\n\nText to rewrite:\n" + text
    )

    if is_ollama:
        payload = {
            "model": "gpt-oss:20b",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            "temperature": 0.2,
            "max_tokens": 2048
        }
        chat_url = url if "/api/chat" in url else url.rstrip("/") + "/api/chat"
    else:
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            "max_tokens": 2048,
            "temperature": 0.2,
        }
        chat_url = url
    try:
        resp = requests.post(chat_url, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        # Parse response robustly
        try:
            content, parsed_json, raw_text = _parse_llm_response(resp, is_ollama=is_ollama)
        except Exception as ex:
            print(f"[ERROR] Failed to parse response: {ex}\n{traceback.format_exc()}")
            content, parsed_json, raw_text = (None, None, resp.text)
        # Write per-chunk LLM debug if path is set
        try:
            if LLM_DEBUG_PATH:
                with open(LLM_DEBUG_PATH, 'a', encoding='utf-8') as dbg:
                    assembled_preview = content[:600] if isinstance(content, str) else ''
                    dbg.write(f"--- LLM RESPONSE ---\nstatus={resp.status_code}\nurl={chat_url}\nchunk_preview={repr(text[:200])}\nparsed_present={parsed_json is not None}\nparsed_summary={repr(str(parsed_json))[:1000]}\nassembled_preview={repr(assembled_preview)[:1000]}\nraw_preview={repr(raw_text)[:240]}\n\n")
        except Exception as ex:
            print(f"[WARN] Could not write LLM debug: {ex}")
        # Decide what to return
        if content and isinstance(content, str) and content.strip():
            return content.strip()
        # Try a few fallbacks based on parsed JSON
        if parsed_json is not None:
            # Try typical locations again
            if isinstance(parsed_json, dict):
                # choices -> message -> content
                try:
                    return parsed_json['choices'][0]['message']['content'].strip()
                except Exception:
                    pass
                # message -> content
                try:
                    return parsed_json['message']['content'].strip()
                except Exception:
                    pass
                # content
                try:
                    if isinstance(parsed_json.get('content'), str) and parsed_json.get('content').strip():
                        return parsed_json['content'].strip()
                except Exception:
                    pass
                # output lists
                try:
                    out = parsed_json.get('output')
                    if isinstance(out, list):
                        texts = []
                        for item in out:
                            if isinstance(item, dict):
                                if 'content' in item:
                                    texts.append(item['content'])
                                elif 'text' in item:
                                    texts.append(item['text'])
                        if texts:
                            return '\n'.join(texts).strip()
                except Exception:
                    pass
        # as last resort return raw text (may be NDJSON, but better than empty)
        return raw_text.strip()
    except Exception as e:
        print(f"[ERROR] LLM call failed: {e}")
        return "[REWRITE ERROR] " + text[:200]

def main():
    parser = argparse.ArgumentParser(description="Rewrite a text file in chunks using LLM.")
    parser.add_argument('--input', required=True, help='Input text file')
    parser.add_argument('--output', required=True, help='Output rewritten file')
    parser.add_argument('--llm_api', default=None, help='OpenAI-compatible API endpoint (default: OpenAI)')
    parser.add_argument('--api_key', default=None, help='API key for LLM (if needed)')
    parser.add_argument('--chunk_size', type=int, default=1000, help='Chunk size (default: 1000)')
    parser.add_argument('--overlap', type=int, default=200, help='Chunk overlap (default: 200)')
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        text = f.read()
    chunks = chunk_text(text, chunk_size=args.chunk_size, overlap=args.overlap)
    print(f"Split into {len(chunks)} chunks.")
    # Dump per-chunk diagnostics to a debug file for inspection
    debug_path = args.output + ".chunks_debug.txt"
    with open(debug_path, 'w', encoding='utf-8') as dbg:
        dbg.write(f"Input: {args.input}\nTotal length: {len(text)}\nChunks: {len(chunks)}\n\n")
        for i, c in enumerate(chunks):
            dbg.write(f"--- Chunk {i+1} ---\nlen={len(c)}\nwhitespace_only={len(c.strip())==0}\npreview={repr(c[:200])}\n\n")
    print(f"Wrote chunk debug to {debug_path}")

    # Set LLM debug path (per-chunk LLM response logs)
    global LLM_DEBUG_PATH
    LLM_DEBUG_PATH = args.output + ".llm_debug.txt"
    # initialise/clear the file
    with open(LLM_DEBUG_PATH, 'w', encoding='utf-8') as dd:
        dd.write(f"LLM debug for input={args.input}\n\n")
    print(f"LLM debug path set to {LLM_DEBUG_PATH}")

    with open(args.output, 'w', encoding='utf-8') as f:
        for i, chunk in enumerate(chunks):
            # Diagnostic: show chunk size and preview to help identify empty/whitespace-only chunks
            print(f"Rewriting chunk {i+1}/{len(chunks)}... length={len(chunk)} whitespace_only={len(chunk.strip())==0}")
            preview = chunk.strip().replace('\n', ' ')[:120] if chunk.strip() else '<EMPTY>'
            print(f"Chunk preview: {preview!r}")
            if not chunk.strip():
                rewritten = "[EMPTY CHUNK]"
            else:
                rewritten = rewrite_text(chunk, llm_api=args.llm_api, api_key=args.api_key)
            f.write(f"\n\n=== [Chunk {i+1}] ===\n")
            f.write(rewritten)
            f.flush()
            time.sleep(1)
    print(f"Done. Output written to {args.output}")

if __name__ == "__main__":
    main()
