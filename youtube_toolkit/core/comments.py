"""YouTube comment downloader — pure innertube API, no page fetches, no cookies."""
import asyncio
import json
import textwrap
import time
from datetime import datetime
from pathlib import Path

import aiohttp
import requests as _req
from fpdf import FPDF

from .utils import sanitize_filename, extract_video_id

SORT_BY_POPULAR = 0
SORT_BY_RECENT = 1

# Stable innertube WEB client config — hardcoded so no page fetch needed
_IK = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
_CTX = {
    "client": {
        "hl": "en", "gl": "US",
        "clientName": "WEB",
        "clientVersion": "2.20240320.00.00",
    }
}
_YT_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "X-YouTube-Client-Name": "1",
    "X-YouTube-Client-Version": "2.20240320.00.00",
    "Origin": "https://www.youtube.com",
    "Referer": "https://www.youtube.com/",
}

# Route YouTube calls through Cloudflare Worker proxy to avoid HF Space IP block
_CF_PROXY = "https://ytbro.redstudio2595.workers.dev/ytproxy"
_CF_PROXY_BATCH = "https://ytbro.redstudio2595.workers.dev/ytproxy_batch"


def _innertube_post(endpoint, payload):
    """POST to YouTube innertube via CF Worker proxy (CF IPs not blocked by YouTube)."""
    target = f"https://www.youtube.com/youtubei/v1/{endpoint}?key={_IK}"
    r = _req.post(
        _CF_PROXY,
        json={"target": target, "headers": _YT_HEADERS, "body": payload},
        timeout=25,
    )
    return r.json() if r.ok else {}


def _search_dict(obj, key):
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if k == key:
                    yield v
                else:
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)


def _parse_comments(data, owner_channel_id=None):
    """Extract comments, next-page continuations, reply continuations from innertube response."""
    comments, next_conts, reply_conts = [], [], []
    actions = (
        list(_search_dict(data, "reloadContinuationItemsCommand"))
        + list(_search_dict(data, "appendContinuationItemsAction"))
    )
    for action in actions:
        target = action.get("targetId", "")
        for item in action.get("continuationItems", []):
            if target in (
                "comments-section",
                "engagement-panel-comments-section",
                "shorts-engagement-panel-comments-section",
            ):
                if "continuationItemRenderer" in item:
                    next_conts.extend(_search_dict(item, "continuationEndpoint"))
                else:
                    # Precise path to reply continuation — broad search finds wrong endpoints
                    thread = item.get("commentThreadRenderer", {})
                    for content in (thread.get("replies", {})
                                    .get("commentRepliesRenderer", {})
                                    .get("contents", [])):
                        ep = content.get("continuationItemRenderer", {}).get("continuationEndpoint")
                        if ep:
                            reply_conts.append(ep)
            elif target.startswith("comment-replies-item"):
                if "continuationItemRenderer" in item:
                    btn = next(_search_dict(item, "buttonRenderer"), None)
                    if btn and "command" in btn:
                        reply_conts.append(btn["command"])

    toolbar_states = {
        p["key"]: p
        for p in _search_dict(data, "engagementToolbarStateEntityPayload")
    }
    for comment in reversed(list(_search_dict(data, "commentEntityPayload"))):
        try:
            props = comment["properties"]
            cid = props["commentId"]
            author = comment["author"]
            toolbar = comment["toolbar"]
            ts = toolbar_states.get(props.get("toolbarStateKey", ""), {})
            comments.append({
                "cid": cid,
                "text": props["content"]["content"],
                "time": props["publishedTime"],
                "author": author["displayName"],
                "channel": author["channelId"],
                "votes": toolbar.get("likeCountNotliked", "0").strip() or "0",
                "replies": toolbar.get("replyCount", 0),
                "photo": author.get("avatarThumbnailUrl", ""),
                "heart": ts.get("heartState", "") == "TOOLBAR_HEART_STATE_HEARTED",
                "reply": "." in cid,
                "is_creator": bool(
                    owner_channel_id and author.get("channelId") == owner_channel_id
                ),
            })
        except (KeyError, TypeError):
            continue
    return comments, next_conts, reply_conts


def _get_sort_menu(video_id):
    """
    Use innertube /next (POST) to get comment sort continuations + owner channel ID.
    Returns (sort_menu, owner_channel_id).
    """
    data = _innertube_post("next", {"context": _CTX, "videoId": video_id})

    # Extract video owner channel ID (UC... format) from the response
    owner_channel_id = next(
        (bid for bid in _search_dict(data, "browseId") if isinstance(bid, str) and bid.startswith("UC")),
        None,
    )

    sort_menu = next(_search_dict(data, "sortFilterSubMenuRenderer"), {}).get("subMenuItems", [])

    if not sort_menu:
        # Need to follow an intermediate continuation to reach the comments panel
        for cont_ep in _search_dict(data, "continuationEndpoint"):
            cmd = cont_ep.get("continuationCommand", {})
            token = cmd.get("token") or cmd.get("continuation")
            if not token:
                continue
            data2 = _innertube_post("next", {"context": _CTX, "continuation": token})
            sort_menu = next(_search_dict(data2, "sortFilterSubMenuRenderer"), {}).get("subMenuItems", [])
            if sort_menu:
                break

    return sort_menu, owner_channel_id


async def _async_innertube(session, endpoint, payload):
    """POST via CF Worker proxy (async)."""
    target = f"https://www.youtube.com/youtubei/v1/{endpoint}?key={_IK}"
    proxy_body = {"target": target, "headers": _YT_HEADERS, "body": payload}
    for attempt in range(3):
        try:
            async with session.post(
                _CF_PROXY,
                json=proxy_body,
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status in (403, 413):
                    return {}
                if resp.status == 429:
                    await asyncio.sleep(2 * (attempt + 1))
        except (asyncio.TimeoutError, aiohttp.ClientError):
            if attempt < 2:
                await asyncio.sleep(0.5)
    return {}


async def _async_innertube_batch(session, payloads):
    """Send BATCH innertube /next requests in a single CF Worker call (CF fans out with Promise.all)."""
    target = f"https://www.youtube.com/youtubei/v1/next?key={_IK}"
    proxy_requests = [
        {"target": target, "headers": _YT_HEADERS, "body": p}
        for p in payloads
    ]
    for attempt in range(3):
        try:
            async with session.post(
                _CF_PROXY_BATCH,
                json=proxy_requests,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 200:
                    items = await resp.json()
                    return [
                        json.loads(it["body"]) if it.get("status") == 200 else {}
                        for it in items
                    ]
                if resp.status in (403, 413):
                    return [{} for _ in payloads]
                if resp.status == 429:
                    await asyncio.sleep(2 * (attempt + 1))
        except (asyncio.TimeoutError, aiohttp.ClientError):
            if attempt < 2:
                await asyncio.sleep(0.5)
    return [{} for _ in payloads]


async def _fetch_replies(session, cont_ep, results, stats, owner_channel_id=None):
    conts = [cont_ep]
    seen_tokens = set()
    consecutive_failures = 0
    while conts:
        ep = conts.pop(0)
        token = (
            (ep.get("continuationCommand") or {}).get("token")
            or (ep.get("continuationCommand") or {}).get("continuation")
            or next(_search_dict(ep, "token"), None)
            or next(_search_dict(ep, "continuation"), None)
        )
        if not token or not isinstance(token, str) or len(token) < 10:
            continue
        if token in seen_tokens:
            continue
        seen_tokens.add(token)

        resp = await _async_innertube(session, "next", {"context": _CTX, "continuation": token})
        if not resp:
            consecutive_failures += 1
            if consecutive_failures >= 3:
                break
            continue
        consecutive_failures = 0

        comments, _, more = _parse_comments(resp, owner_channel_id)
        results.extend(comments)
        stats["replies"] += len(comments)
        for ep2 in more:
            t = (
                (ep2.get("continuationCommand") or {}).get("token")
                or (ep2.get("continuationCommand") or {}).get("continuation")
                or next(_search_dict(ep2, "token"), None)
            )
            if t and isinstance(t, str) and len(t) > 10 and t not in seen_tokens:
                conts.append(ep2)


async def _download_async(video_id, sort_by, max_comments, on_progress, sort_menu, owner_channel_id=None):
    if not sort_menu or sort_by >= len(sort_menu):
        raise RuntimeError("Could not get comment sort menu from YouTube.")

    all_top, all_replies = [], []
    stats = {"top": 0, "replies": 0}
    last_cb = time.time()

    # Extract initial continuation from the sort menu
    service_ep = sort_menu[sort_by].get("serviceEndpoint", {})
    cont_cmd = service_ep.get("continuationCommand", {})
    token = cont_cmd.get("token") or cont_cmd.get("continuation", "")
    if not token:
        raise RuntimeError("No continuation token found in sort menu.")

    async with aiohttp.ClientSession() as session:
        reply_tasks = []
        continuations = [token]

        BATCH = 10  # fetch 10 pages in parallel
        failures = 0
        while continuations:
            if max_comments > 0 and (stats["top"] + stats["replies"]) >= max_comments:
                break

            # Take up to BATCH tokens at once
            batch = []
            while continuations and len(batch) < BATCH:
                batch.append(continuations.pop(0))

            # Fetch all pages in a single CF Worker batch call (CF fans out to YouTube in parallel)
            payloads = [{"context": _CTX, "continuation": t} for t in batch]
            results = await _async_innertube_batch(session, payloads)

            got_any = False
            for tok, resp in zip(batch, results):
                if not resp:
                    failures += 1
                    if failures < 3:
                        continuations.insert(0, tok)  # retry
                    continue
                failures = 0
                if next(_search_dict(resp, "externalErrorMessage"), None):
                    continue
                got_any = True

                comments, next_c, reply_c = _parse_comments(resp, owner_channel_id)
                for c in comments:
                    if not c["reply"]:
                        all_top.append(c)
                        stats["top"] += 1

                for ep in next_c:
                    t = (ep.get("continuationCommand", {}).get("token")
                         or ep.get("continuationCommand", {}).get("continuation")
                         or next(_search_dict(ep, "token"), None)
                         or next(_search_dict(ep, "continuation"), None))
                    if t and isinstance(t, str) and len(t) > 10:
                        continuations.append(t)

                # Launch reply fetchers as background tasks
                for ep in reply_c:
                    task = asyncio.ensure_future(
                        _fetch_replies(session, ep, all_replies, stats, owner_channel_id)
                    )
                    reply_tasks.append(task)

            if failures >= 3 and not got_any:
                break

            now = time.time()
            if on_progress and now - last_cb > 0.4:
                on_progress({"total": stats["top"] + stats["replies"]})
                last_cb = now

        # Wait for all reply tasks
        if reply_tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*reply_tasks), timeout=180)
            except asyncio.TimeoutError:
                pass

    if on_progress:
        on_progress({"total": stats["top"] + stats["replies"], "done": True})

    # Merge replies under parents
    reply_map = {}
    for r in all_replies:
        if "." in r.get("cid", ""):
            reply_map.setdefault(r["cid"].rsplit(".", 1)[0], []).append(r)
    final = []
    for c in all_top:
        final.append(c)
        if c["cid"] in reply_map:
            final.extend(reply_map[c["cid"]])

    return final[:max_comments] if max_comments > 0 else final


# ── Public API ────────────────────────────────────────────────────

def download_comments(video_url, sort_by=SORT_BY_RECENT, max_comments=0, on_progress=None):
    """Download comments via innertube POST API only — no page fetches, no cookies, permanent.

    Returns (comments_list, title, comment_count).
    """
    video_id = extract_video_id(video_url) or video_url

    # Title via oEmbed (lightweight, not blocked)
    try:
        r = _req.get(
            f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json",
            timeout=8,
        )
        title = r.json().get("title", video_id) if r.ok else video_id
    except Exception:
        title = video_id

    sort_menu, owner_channel_id = _get_sort_menu(video_id)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        raw = loop.run_until_complete(
            _download_async(video_id, sort_by, max_comments, on_progress, sort_menu, owner_channel_id)
        )
    finally:
        loop.close()

    return raw, title, len(raw)


def build_structured_comments(raw_comments):
    """Convert raw comments to structured list with reply threading."""
    comments, parent_map = [], {}
    for i, raw in enumerate(raw_comments):
        cid, is_reply = raw.get("cid", ""), raw.get("reply", False)
        author, text = raw.get("author", "Unknown"), raw.get("text", "")
        pa, pn, pp = "", 0, ""
        if is_reply and "." in cid:
            pid = cid.rsplit(".", 1)[0]
            if pid in parent_map:
                pa = parent_map[pid]["author"]
                pn = parent_map[pid]["number"]
                pp = parent_map[pid]["preview"]
        num = i + 1
        if not is_reply:
            preview = text[:80].replace("\n", " ") + ("..." if len(text) > 80 else "")
            parent_map[cid] = {"author": author, "number": num, "preview": preview}
        auth_display = pa if pa.startswith("@") else f"@{pa}" if pa else ""
        comments.append({
            "author": author, "text": text, "time": raw.get("time", ""),
            "likes": raw.get("votes", "0"), "reply_count": raw.get("replies", 0),
            "is_reply": is_reply, "parent_author": auth_display,
            "parent_comment_number": pn, "parent_text_preview": pp,
            "comment_id": cid, "heart": raw.get("heart", False),
            "is_creator": raw.get("is_creator", False),
        })
    return comments


# ── Export Functions ──────────────────────────────────────────────

def _fmt(i, c):
    heart = " [HEARTED]" if c["heart"] else ""
    likes = str(c["likes"]) if c["likes"] else "0"
    reply_to = ""
    reply_detail = ""
    if c["is_reply"] and c["parent_author"] and c["parent_comment_number"]:
        reply_to = f"{c['parent_author']} (Comment #{c['parent_comment_number']})"
        reply_detail = (
            f"In reply to Comment #{c['parent_comment_number']} "
            f"by {c['parent_author']}: \"{c['parent_text_preview']}\""
        )
    return {
        "num": i, "author": c["author"], "time": c["time"], "likes": likes,
        "heart": heart, "reply_to": reply_to, "reply_detail": reply_detail,
        "reply_count": c.get("reply_count", 0), "text": c["text"],
        "is_reply": c["is_reply"],
    }


def save_comments_txt(comments, video_id, output_dir, title=None):
    safe = sanitize_filename(title) if title else video_id
    fp = Path(output_dir) / f"comments_{safe}.txt"
    top = sum(1 for c in comments if not c["is_reply"])
    reps = sum(1 for c in comments if c["is_reply"])
    with open(fp, "w", encoding="utf-8") as f:
        f.write(f"{'='*70}\nYOUTUBE COMMENTS EXPORT\n"
                f"Video: https://www.youtube.com/watch?v={video_id}\n")
        f.write(f"Total: {len(comments)} | Top-level: {top} | Replies: {reps}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}\n\n")
        for i, c in enumerate(comments, 1):
            d = _fmt(i, c)
            if d["is_reply"]:
                f.write(f"    --- REPLY #{d['num']} ---\n"
                        f"      Author: {d['author']}  |  {d['time']}  |  Likes: {d['likes']}{d['heart']}\n"
                        f"      Reply To: {d['reply_to']}\n")
                if d["reply_detail"]:
                    f.write(f"      Context: {d['reply_detail']}\n")
                for ln in d["text"].split("\n"):
                    f.write(f"        {ln}\n")
            else:
                f.write(f"--- COMMENT #{d['num']} ---\n"
                        f"  Author: {d['author']}  |  {d['time']}  |  Likes: {d['likes']}{d['heart']}\n")
                if d["reply_count"]:
                    f.write(f"  Replies: {d['reply_count']}\n")
                for ln in d["text"].split("\n"):
                    f.write(f"    {ln}\n")
            f.write("\n")
    return str(fp)


def save_comments_md(comments, video_id, output_dir, title=None):
    safe = sanitize_filename(title) if title else video_id
    fp = Path(output_dir) / f"comments_{safe}.md"
    top = sum(1 for c in comments if not c["is_reply"])
    reps = sum(1 for c in comments if c["is_reply"])
    with open(fp, "w", encoding="utf-8") as f:
        f.write(f"# YouTube Comments\n\n"
                f"- **Video:** https://www.youtube.com/watch?v={video_id}\n"
                f"- **Total:** {len(comments)} | Top-level: {top} | Replies: {reps}\n"
                f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
        for i, c in enumerate(comments, 1):
            d = _fmt(i, c)
            if d["is_reply"]:
                f.write(f"#### > Reply #{d['num']} to {d['reply_to']}\n\n"
                        f"| | |\n|---|---|\n| **Author** | {d['author']} |\n"
                        f"| **Posted** | {d['time']} |\n| **Likes** | {d['likes']}{d['heart']} |\n"
                        f"| **Replying To** | {d['reply_to']} |\n\n> > {d['text']}\n\n---\n\n")
            else:
                f.write(f"### Comment #{d['num']}\n\n| | |\n|---|---|\n"
                        f"| **Author** | {d['author']} |\n| **Posted** | {d['time']} |\n"
                        f"| **Likes** | {d['likes']}{d['heart']} |\n")
                if d["reply_count"]:
                    f.write(f"| **Replies** | {d['reply_count']} |\n")
                f.write(f"\n> {d['text']}\n\n---\n\n")
    return str(fp)


def save_comments_pdf(comments, video_id, output_dir, title=None):
    safe = sanitize_filename(title) if title else video_id
    fp = Path(output_dir) / f"comments_{safe}.pdf"
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    san = lambda t: t.encode("latin-1", "replace").decode("latin-1")
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, san(f"YouTube Comments - {video_id}"), new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 6, san(f"Total: {len(comments)} | Date: {datetime.now().strftime('%Y-%m-%d')}"),
             new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    for i, c in enumerate(comments, 1):
        d = _fmt(i, c)
        pdf.set_font("Helvetica", "B", 9 if d["is_reply"] else 10)
        x = 20 if d["is_reply"] else 10
        pdf.set_x(x)
        pdf.cell(0, 5, san(f"{'REPLY' if d['is_reply'] else 'COMMENT'} #{d['num']}"),
                 new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x)
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(0, 4, san(f"{d['author']} | {d['time']} | Likes: {d['likes']}{d['heart']}"),
                 new_x="LMARGIN", new_y="NEXT")
        if d["is_reply"] and d["reply_to"]:
            pdf.set_x(x)
            pdf.set_font("Helvetica", "I", 7)
            pdf.cell(0, 4, san(f"Reply to: {d['reply_to']}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(x)
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 4, textwrap.fill(san(d["text"]), width=90))
        pdf.ln(2)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)
    pdf.output(str(fp))
    return str(fp)


def save_comments_json(comments, video_id, output_dir, title=None):
    safe = sanitize_filename(title) if title else video_id
    fp = Path(output_dir) / f"comments_{safe}.json"
    with open(fp, "w", encoding="utf-8") as f:
        json.dump({
            "video_id": video_id, "total": len(comments),
            "date": datetime.now().isoformat(), "comments": comments,
        }, f, ensure_ascii=False, indent=2)
    return str(fp)
