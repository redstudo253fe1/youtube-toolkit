"""Upload content to free paste services — returns AI-readable public URL."""
import requests


def upload_content(content: str, filename: str = "content.md") -> str | None:
    """Upload text/markdown to paste.rs (primary) or 0x0.st (fallback).

    Returns a public URL that ChatGPT / Perplexity / Claude can read,
    or None if both services fail.
    """
    # ── Primary: paste.rs ─────────────────────────────────────
    try:
        resp = requests.post(
            "https://paste.rs/",
            data=content.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
            timeout=20,
        )
        if resp.status_code in (200, 201):
            url = resp.text.strip()
            if url.startswith("http"):
                return url
    except Exception:
        pass

    # ── Fallback: 0x0.st ──────────────────────────────────────
    try:
        resp = requests.post(
            "https://0x0.st",
            files={"file": (filename, content.encode("utf-8"), "text/plain")},
            timeout=20,
        )
        if resp.status_code == 200:
            url = resp.text.strip()
            if url.startswith("http"):
                return url
    except Exception:
        pass

    return None
