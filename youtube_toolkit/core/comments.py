"""YouTube comment downloader — yt-dlp auth + fast parallel engine."""
import asyncio
import json
import re
import time
import textwrap
import logging
from datetime import datetime
from pathlib import Path

import aiohttp
from fpdf import FPDF
from yt_dlp import YoutubeDL

from .utils import sanitize_filename

SORT_BY_POPULAR = 0
SORT_BY_RECENT = 1

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'


# ── yt-dlp: get page data (cookies + auth, no 429) ───────────────

def _get_browser_cookies():
    """Probe browsers for usable cookies, return (browser_name,) or None."""
    _log = logging.getLogger('yt-dlp')
    _prev = _log.level
    _log.setLevel(logging.CRITICAL)
    result = None
    for browser in ('firefox', 'chrome', 'edge', 'opera', 'brave'):
        try:
            opts = {'quiet': True, 'no_warnings': True, 'cookiesfrombrowser': (browser,)}
            with YoutubeDL(opts) as ydl:
                list(ydl.cookiejar)
            result = (browser,)
            break
        except Exception:
            continue
    _log.setLevel(_prev)
    return result


def _fetch_page_with_ytdlp(video_url):
    """Use yt-dlp to fetch video page — gets title and avoids 429.
    Returns (html, cookies_dict, title).
    """
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
    }
    browser_cookies = _get_browser_cookies()
    if browser_cookies:
        ydl_opts['cookiesfrombrowser'] = browser_cookies

    with YoutubeDL(ydl_opts) as ydl:
        # Extract just video info (no comments — that's slow)
        info = ydl.extract_info(video_url, download=False)
        title = info.get('title', 'Unknown')

        # Get cookies from yt-dlp's session for our fast engine
        cookies = {}
        for cookie in ydl.cookiejar:
            if '.youtube.com' in cookie.domain:
                cookies[cookie.name] = cookie.value

    return cookies, title


# ── Fast parallel comment engine (original) ───────────────────────

YT_CFG_RE = r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;'
YT_INITIAL_DATA_RE = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;\s*(?:var\s+meta|</script|\n)'


def _search_dict(partial, search_key):
    stack = [partial]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for k, v in current.items():
                if k == search_key:
                    yield v
                else:
                    stack.append(v)
        elif isinstance(current, list):
            stack.extend(current)


def _parse_response(data):
    comments, next_conts, reply_conts = [], [], []
    actions = list(_search_dict(data, 'reloadContinuationItemsCommand')) + \
              list(_search_dict(data, 'appendContinuationItemsAction'))
    for action in actions:
        target = action.get('targetId', '')
        for item in action.get('continuationItems', []):
            if target in ['comments-section', 'engagement-panel-comments-section',
                          'shorts-engagement-panel-comments-section']:
                if 'continuationItemRenderer' in item:
                    next_conts.extend(list(_search_dict(item, 'continuationEndpoint')))
                else:
                    reply_conts.extend(list(_search_dict(item, 'continuationEndpoint')))
            elif target.startswith('comment-replies-item'):
                if 'continuationItemRenderer' in item:
                    btn = next(_search_dict(item, 'buttonRenderer'), None)
                    if btn and 'command' in btn:
                        reply_conts.append(btn['command'])

    toolbar_states = {p['key']: p for p in _search_dict(data, 'engagementToolbarStateEntityPayload')}
    for comment in reversed(list(_search_dict(data, 'commentEntityPayload'))):
        try:
            props = comment['properties']
            cid = props['commentId']
            author = comment['author']
            toolbar = comment['toolbar']
            ts = toolbar_states.get(props.get('toolbarStateKey', ''), {})
            comments.append({
                'cid': cid, 'text': props['content']['content'],
                'time': props['publishedTime'], 'author': author['displayName'],
                'channel': author['channelId'],
                'votes': toolbar.get('likeCountNotliked', '0').strip() or '0',
                'replies': toolbar.get('replyCount', 0),
                'photo': author.get('avatarThumbnailUrl', ''),
                'heart': ts.get('heartState', '') == 'TOOLBAR_HEART_STATE_HEARTED',
                'reply': '.' in cid,
            })
        except (KeyError, TypeError):
            continue
    return comments, next_conts, reply_conts


async def _async_post(session, endpoint, ytcfg):
    url = 'https://www.youtube.com' + endpoint['commandMetadata']['webCommandMetadata']['apiUrl']
    data = {'context': ytcfg['INNERTUBE_CONTEXT'], 'continuation': endpoint['continuationCommand']['token']}
    for attempt in range(3):
        try:
            async with session.post(url, params={'key': ytcfg['INNERTUBE_API_KEY']},
                                    json=data, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status in [403, 413]:
                    return {}
                if resp.status == 429:
                    await asyncio.sleep(2 * (attempt + 1))
        except (asyncio.TimeoutError, aiohttp.ClientError):
            if attempt < 2:
                await asyncio.sleep(0.5)
    return {}


async def _reply_worker(session, ytcfg, queue, results, stats):
    while True:
        try:
            rc = await asyncio.wait_for(queue.get(), timeout=15.0)
        except asyncio.TimeoutError:
            break
        if rc is None:
            break
        conts = [rc]
        while conts:
            resp = await _async_post(session, conts.pop(0), ytcfg)
            if not resp:
                break
            comments, _, more = _parse_response(resp)
            results.extend(comments)
            stats['replies'] += len(comments)
            conts.extend(more)
        queue.task_done()


async def _download_comments_fast(video_url, cookies, sort_by, max_comments, on_progress):
    """Fast parallel comment download using auth cookies from yt-dlp."""
    import requests as req

    # Build cookie header from yt-dlp session
    cookie_str = '; '.join(f'{k}={v}' for k, v in cookies.items())
    if 'SOCS' not in cookies:
        cookie_str += '; SOCS=CAI'

    headers = {
        'User-Agent': USER_AGENT,
        'Accept-Language': 'en-US,en;q=0.9',
        'Cookie': cookie_str,
    }

    # Fetch the page with authenticated cookies
    sync_session = req.Session()
    sync_session.headers.update(headers)
    for k, v in cookies.items():
        sync_session.cookies.set(k, v, domain='.youtube.com')
    sync_session.cookies.set('SOCS', 'CAI', domain='.youtube.com')

    resp = sync_session.get(video_url, timeout=15)
    final_url = str(resp.url)
    if resp.status_code == 429 or 'google.com/sorry' in final_url:
        sync_session.close()
        raise RuntimeError("YouTube rate-limited this IP. Try again later or use a VPN.")
    html = resp.text

    m = re.search(YT_CFG_RE, html)
    if not m:
        sync_session.close()
        raise RuntimeError("Could not parse YouTube page. Try again in a few minutes.")
    ytcfg = json.loads(m.group(1))

    m = re.search(YT_INITIAL_DATA_RE, html)
    if not m:
        sync_session.close()
        raise RuntimeError("Could not parse YouTube page data. Try again.")
    data = json.loads(m.group(1))

    item_section = next(_search_dict(data, 'itemSectionRenderer'), None)
    if not item_section:
        sync_session.close()
        return []
    if not next(_search_dict(item_section, 'continuationItemRenderer'), None):
        sync_session.close()
        return []

    sort_menu = next(_search_dict(data, 'sortFilterSubMenuRenderer'), {}).get('subMenuItems', [])
    if not sort_menu:
        sl = next(_search_dict(data, 'sectionListRenderer'), {})
        fc = list(_search_dict(sl, 'continuationEndpoint'))
        if fc:
            r2 = sync_session.post(
                'https://www.youtube.com' + fc[0]['commandMetadata']['webCommandMetadata']['apiUrl'],
                params={'key': ytcfg['INNERTUBE_API_KEY']},
                json={'context': ytcfg['INNERTUBE_CONTEXT'], 'continuation': fc[0]['continuationCommand']['token']},
                timeout=15,
            )
            data = r2.json() if r2.status_code == 200 else {}
        sort_menu = next(_search_dict(data, 'sortFilterSubMenuRenderer'), {}).get('subMenuItems', [])

    sync_session.close()

    if not sort_menu or sort_by >= len(sort_menu):
        return []

    # Fast parallel download with 30 workers
    all_top, all_replies = [], []
    reply_queue = asyncio.Queue()
    stats = {'replies': 0, 'pages': 0, 'top': 0}

    connector = aiohttp.TCPConnector(limit=50, limit_per_host=50)
    aio_headers = {
        'User-Agent': USER_AGENT,
        'Cookie': cookie_str + ('; SOCS=CAI' if 'SOCS' not in cookies else ''),
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json',
        'X-Youtube-Client-Name': '1',
        'X-Youtube-Client-Version': ytcfg.get('INNERTUBE_CLIENT_VERSION', '2.20240320.00.00'),
        'Origin': 'https://www.youtube.com',
        'Referer': video_url,
    }

    async with aiohttp.ClientSession(connector=connector, headers=aio_headers) as session:
        workers = [asyncio.create_task(_reply_worker(session, ytcfg, reply_queue, all_replies, stats))
                   for _ in range(30)]
        continuations = [sort_menu[sort_by]['serviceEndpoint']]
        last_cb = time.time()

        while continuations:
            if max_comments > 0 and (stats['top'] + stats['replies']) >= max_comments:
                break
            resp_data = await _async_post(session, continuations.pop(0), ytcfg)
            if not resp_data:
                break
            if next(_search_dict(resp_data, 'externalErrorMessage'), None):
                break

            comments, next_c, reply_c = _parse_response(resp_data)
            for c in comments:
                if not c['reply']:
                    all_top.append(c)
                    stats['top'] += 1
            for rc in reply_c:
                await reply_queue.put(rc)
            continuations.extend(next_c)
            stats['pages'] += 1

            if on_progress and time.time() - last_cb > 0.3:
                on_progress({**stats, 'total': stats['top'] + stats['replies']})
                last_cb = time.time()

        for _ in range(30):
            await reply_queue.put(None)
        try:
            await asyncio.wait_for(asyncio.gather(*workers), timeout=60)
        except asyncio.TimeoutError:
            pass

    if on_progress:
        on_progress({**stats, 'total': stats['top'] + stats['replies'], 'done': True})

    # Merge replies under parents
    reply_map = {}
    for r in all_replies:
        if '.' in r.get('cid', ''):
            reply_map.setdefault(r['cid'].rsplit('.', 1)[0], []).append(r)
    final = []
    for c in all_top:
        final.append(c)
        if c['cid'] in reply_map:
            final.extend(reply_map[c['cid']])

    return final[:max_comments] if max_comments > 0 else final


# ── Public API ────────────────────────────────────────────────────

def download_comments(video_url, sort_by=SORT_BY_RECENT, max_comments=0,
                      on_progress=None):
    """Download comments: yt-dlp for auth + fast parallel engine for speed.

    Returns (comments_list, title, comment_count).
    """
    # Step 1: Use yt-dlp to get authenticated cookies + title (no 429)
    cookies, title = _fetch_page_with_ytdlp(video_url)

    # Step 2: Fast parallel download with those cookies
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        raw = loop.run_until_complete(
            _download_comments_fast(video_url, cookies, sort_by, max_comments, on_progress)
        )
    finally:
        loop.close()

    return raw, title, len(raw)


def build_structured_comments(raw_comments):
    """Convert raw comments to structured list with reply threading."""
    comments, parent_map = [], {}
    for i, raw in enumerate(raw_comments):
        cid, is_reply = raw.get('cid', ''), raw.get('reply', False)
        author, text = raw.get('author', 'Unknown'), raw.get('text', '')
        pa, pn, pp = '', 0, ''
        if is_reply and '.' in cid:
            pid = cid.rsplit('.', 1)[0]
            if pid in parent_map:
                pa, pn, pp = parent_map[pid]['author'], parent_map[pid]['number'], parent_map[pid]['preview']
        num = i + 1
        if not is_reply:
            preview = text[:80].replace('\n', ' ') + ('...' if len(text) > 80 else '')
            parent_map[cid] = {'author': author, 'number': num, 'preview': preview}
        auth_display = pa if pa.startswith('@') else f'@{pa}' if pa else ''
        comments.append({
            'author': author, 'text': text, 'time': raw.get('time', ''),
            'likes': raw.get('votes', '0'), 'reply_count': raw.get('replies', 0),
            'is_reply': is_reply, 'parent_author': auth_display,
            'parent_comment_number': pn, 'parent_text_preview': pp,
            'comment_id': cid, 'heart': raw.get('heart', False),
        })
    return comments


# ── Export Functions ──

def _fmt(i, c):
    heart = ' [HEARTED]' if c['heart'] else ''
    likes = str(c['likes']) if c['likes'] else '0'
    reply_to = ''
    reply_detail = ''
    if c['is_reply'] and c['parent_author'] and c['parent_comment_number']:
        reply_to = f"{c['parent_author']} (Comment #{c['parent_comment_number']})"
        reply_detail = f"In reply to Comment #{c['parent_comment_number']} by {c['parent_author']}: \"{c['parent_text_preview']}\""
    return {'num': i, 'author': c['author'], 'time': c['time'], 'likes': likes,
            'heart': heart, 'reply_to': reply_to, 'reply_detail': reply_detail,
            'reply_count': c.get('reply_count', 0), 'text': c['text'], 'is_reply': c['is_reply']}


def save_comments_txt(comments, video_id, output_dir, title=None):
    safe = sanitize_filename(title) if title else video_id
    fp = Path(output_dir) / f"comments_{safe}.txt"
    top = sum(1 for c in comments if not c['is_reply'])
    reps = sum(1 for c in comments if c['is_reply'])
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(f"{'='*70}\nYOUTUBE COMMENTS EXPORT\nVideo: https://www.youtube.com/watch?v={video_id}\n")
        f.write(f"Total: {len(comments)} | Top-level: {top} | Replies: {reps}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*70}\n\n")
        for i, c in enumerate(comments, 1):
            d = _fmt(i, c)
            if d['is_reply']:
                f.write(f"    --- REPLY #{d['num']} ---\n      Author: {d['author']}  |  {d['time']}  |  Likes: {d['likes']}{d['heart']}\n")
                f.write(f"      Reply To: {d['reply_to']}\n")
                if d['reply_detail']:
                    f.write(f"      Context: {d['reply_detail']}\n")
                for ln in d['text'].split('\n'):
                    f.write(f"        {ln}\n")
            else:
                f.write(f"--- COMMENT #{d['num']} ---\n  Author: {d['author']}  |  {d['time']}  |  Likes: {d['likes']}{d['heart']}\n")
                if d['reply_count']:
                    f.write(f"  Replies: {d['reply_count']}\n")
                for ln in d['text'].split('\n'):
                    f.write(f"    {ln}\n")
            f.write('\n')
    return str(fp)


def save_comments_md(comments, video_id, output_dir, title=None):
    safe = sanitize_filename(title) if title else video_id
    fp = Path(output_dir) / f"comments_{safe}.md"
    top = sum(1 for c in comments if not c['is_reply'])
    reps = sum(1 for c in comments if c['is_reply'])
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(f"# YouTube Comments\n\n- **Video:** https://www.youtube.com/watch?v={video_id}\n")
        f.write(f"- **Total:** {len(comments)} | Top-level: {top} | Replies: {reps}\n")
        f.write(f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n")
        for i, c in enumerate(comments, 1):
            d = _fmt(i, c)
            if d['is_reply']:
                f.write(f"#### > Reply #{d['num']} to {d['reply_to']}\n\n")
                f.write(f"| | |\n|---|---|\n| **Author** | {d['author']} |\n| **Posted** | {d['time']} |\n")
                f.write(f"| **Likes** | {d['likes']}{d['heart']} |\n| **Replying To** | {d['reply_to']} |\n\n")
                f.write(f"> > {d['text']}\n\n---\n\n")
            else:
                f.write(f"### Comment #{d['num']}\n\n| | |\n|---|---|\n| **Author** | {d['author']} |\n")
                f.write(f"| **Posted** | {d['time']} |\n| **Likes** | {d['likes']}{d['heart']} |\n")
                if d['reply_count']:
                    f.write(f"| **Replies** | {d['reply_count']} |\n")
                f.write(f"\n> {d['text']}\n\n---\n\n")
    return str(fp)


def save_comments_pdf(comments, video_id, output_dir, title=None):
    safe = sanitize_filename(title) if title else video_id
    fp = Path(output_dir) / f"comments_{safe}.pdf"
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    san = lambda t: t.encode('latin-1', 'replace').decode('latin-1')
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, san(f'YouTube Comments - {video_id}'), new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 6, san(f'Total: {len(comments)} | Date: {datetime.now().strftime("%Y-%m-%d")}'),
             new_x='LMARGIN', new_y='NEXT', align='C')
    pdf.ln(5)
    for i, c in enumerate(comments, 1):
        d = _fmt(i, c)
        pdf.set_font('Helvetica', 'B', 9 if d['is_reply'] else 10)
        x = 20 if d['is_reply'] else 10
        pdf.set_x(x)
        pdf.cell(0, 5, san(f"{'REPLY' if d['is_reply'] else 'COMMENT'} #{d['num']}"), new_x='LMARGIN', new_y='NEXT')
        pdf.set_x(x)
        pdf.set_font('Helvetica', '', 8)
        pdf.cell(0, 4, san(f"{d['author']} | {d['time']} | Likes: {d['likes']}{d['heart']}"), new_x='LMARGIN', new_y='NEXT')
        if d['is_reply'] and d['reply_to']:
            pdf.set_x(x)
            pdf.set_font('Helvetica', 'I', 7)
            pdf.cell(0, 4, san(f"Reply to: {d['reply_to']}"), new_x='LMARGIN', new_y='NEXT')
        pdf.set_x(x)
        pdf.set_font('Helvetica', '', 8)
        pdf.multi_cell(0, 4, textwrap.fill(san(d['text']), width=90))
        pdf.ln(2)
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)
    pdf.output(str(fp))
    return str(fp)


def save_comments_json(comments, video_id, output_dir, title=None):
    safe = sanitize_filename(title) if title else video_id
    fp = Path(output_dir) / f"comments_{safe}.json"
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump({'video_id': video_id, 'total': len(comments),
                   'date': datetime.now().isoformat(), 'comments': comments}, f, ensure_ascii=False, indent=2)
    return str(fp)
