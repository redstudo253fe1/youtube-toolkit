export default {
  async fetch(request) {
    const url = new URL(request.url);
    const cors = {'Access-Control-Allow-Origin':'*','Access-Control-Allow-Methods':'POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type'};
    if (request.method === 'OPTIONS') return new Response(null, {status:204, headers:cors});
    if (url.pathname === '/ytproxy' && request.method === 'POST') {
      try {
        const {target, headers, body} = await request.json();
        const resp = await fetch(target, {method:'POST', headers: headers||{'Content-Type':'application/json'}, body:JSON.stringify(body)});
        return new Response(await resp.text(), {status:resp.status, headers:{'Content-Type':'application/json',...cors}});
      } catch(e) { return new Response(JSON.stringify({error:e.message}), {status:500, headers:cors}); }
    }
    if (url.pathname === '/ytproxy_batch' && request.method === 'POST') {
      try {
        const requests = await request.json();
        const results = await Promise.all(requests.map(async ({target, headers, body}) => {
          try {
            const resp = await fetch(target, {method:'POST', headers: headers||{'Content-Type':'application/json'}, body:JSON.stringify(body)});
            return {status: resp.status, body: await resp.text()};
          } catch(e) {
            return {status: 500, body: JSON.stringify({error: e.message})};
          }
        }));
        return new Response(JSON.stringify(results), {headers:{'Content-Type':'application/json',...cors}});
      } catch(e) { return new Response(JSON.stringify({error:e.message}), {status:500, headers:cors}); }
    }
    if (url.pathname === '/getproxy' && request.method === 'POST') {
      try {
        const {target} = await request.json();
        const resp = await fetch(target, {headers:{'User-Agent':'Mozilla/5.0'}});
        return new Response(await resp.text(), {status:resp.status, headers:{'Content-Type':'text/plain',...cors}});
      } catch(e) { return new Response(JSON.stringify({error:e.message}), {status:500, headers:cors}); }
    }
    if (url.pathname.startsWith('/youtubei/')) {
      try {
        const target = 'https://www.youtube.com' + url.pathname + url.search;
        const body = request.method === 'POST' ? await request.arrayBuffer() : undefined;
        const resp = await fetch(target, {
          method: request.method,
          headers: {
            'Content-Type': 'application/json',
            'User-Agent': 'com.google.android.apps.youtube.vr.oculus/1.60.19 (Linux; U; Android 12; eureka-user Build/SQ3A.220605.009.A1) gzip',
            'X-Goog-Api-Key': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
          },
          body
        });
        return new Response(resp.body, {status: resp.status, headers: {'Content-Type': 'application/json', ...cors}});
      } catch(e) { return new Response(JSON.stringify({error:e.message}), {status:500, headers:cors}); }
    }
    if (url.pathname === '/aiproxy' && request.method === 'POST') {
      try {
        let payload = await request.json();
        payload.stream = true;
        const resp = await fetch('https://api-hoot.onrender.com/v1/chat/completions', {
          method:'POST',
          headers:{'Content-Type':'application/json','Accept':'text/event-stream'},
          body: JSON.stringify(payload),
        });
        const ct = resp.headers.get('Content-Type') || 'text/event-stream';
        return new Response(resp.body, {
          status: resp.status,
          headers: {'Content-Type': ct, 'Cache-Control':'no-cache', ...cors},
        });
      } catch(e) { return new Response(JSON.stringify({error:e.message}), {status:500, headers:cors}); }
    }
    return new Response(HTML, {headers:{'Content-Type':'text/html; charset=utf-8'}});
  }
};

const HTML = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>ytbro — Analyze YouTube with AI</title>
<meta name="description" content="Free tool to download YouTube comments, captions and AI transcripts. Chat with Claude, GPT, Gemini about any video."/>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
:root{
  --bg:#050510;
  --bg-2:#0a0a18;
  --surface:#0e0e1f;
  --surface-2:#14142b;
  --surface-3:#1a1a38;
  --surface-4:#222247;
  --border:rgba(124,58,237,.18);
  --border-2:rgba(255,255,255,.06);
  --border-3:rgba(255,255,255,.12);
  --a1:#7c3aed;
  --a2:#ec4899;
  --a3:#06b6d4;
  --grad:linear-gradient(135deg,#7c3aed 0%,#ec4899 100%);
  --grad-soft:linear-gradient(135deg,rgba(124,58,237,.15) 0%,rgba(236,72,153,.15) 100%);
  --grad-mesh:radial-gradient(ellipse at top left,rgba(124,58,237,.15),transparent 50%),radial-gradient(ellipse at bottom right,rgba(236,72,153,.12),transparent 50%);
  --text:#e8e8f0;
  --text-2:#b4b4c4;
  --muted:#7d7d95;
  --muted-2:#525268;
  --success:#10b981;
  --error:#ef4444;
  --warn:#f59e0b;
  --info:#06b6d4;
  --r:16px;
  --r-2:12px;
  --r-3:8px;
  --r-4:6px;
  --shadow:0 1px 0 rgba(255,255,255,.04) inset, 0 0 0 1px rgba(255,255,255,.04), 0 8px 24px rgba(0,0,0,.4);
  --shadow-lift:0 1px 0 rgba(255,255,255,.06) inset, 0 0 0 1px rgba(124,58,237,.3), 0 12px 32px rgba(124,58,237,.18);
  --ease:cubic-bezier(.4,0,.2,1);
  --ease-bounce:cubic-bezier(.34,1.56,.64,1);
}
html{scroll-behavior:smooth}
body{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;
  background:var(--bg);
  background-image:var(--grad-mesh);
  background-attachment:fixed;
  color:var(--text);
  min-height:100vh;
  overflow-x:hidden;
  font-feature-settings:'cv11','ss01';
  -webkit-font-smoothing:antialiased;
  text-rendering:optimizeLegibility;
}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--surface-3);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--surface-4)}
::selection{background:rgba(124,58,237,.35);color:#fff}

/* ── Nav ─────────────────────────────────────────────── */
nav{
  position:sticky;top:0;z-index:50;
  background:rgba(5,5,16,.7);
  backdrop-filter:blur(24px) saturate(180%);
  -webkit-backdrop-filter:blur(24px) saturate(180%);
  border-bottom:1px solid var(--border-2);
  padding:.85rem 1.5rem;
  display:flex;align-items:center;justify-content:space-between;
}
.logo{
  font-size:1.4rem;font-weight:800;letter-spacing:-.03em;
  background:var(--grad);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  display:flex;align-items:center;gap:.4rem;
}
.logo-dot{width:6px;height:6px;background:var(--grad);border-radius:50%;animation:pulse 2s var(--ease) infinite}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.3);opacity:.6}}
.logo span{font-weight:300;opacity:.7}
.nav-right{display:flex;align-items:center;gap:.7rem}
.nav-badge{
  font-size:.72rem;font-weight:600;
  background:rgba(124,58,237,.1);
  color:var(--a1);
  border:1px solid rgba(124,58,237,.25);
  padding:.3rem .65rem;border-radius:20px;
}
.nav-badge::before{content:'●';margin-right:.35rem;color:var(--success);font-size:.7em}

/* ── Layout ──────────────────────────────────────────── */
.container{max-width:1080px;margin:0 auto;padding:0 1.25rem}
.hidden{display:none!important}

/* ── Hero ────────────────────────────────────────────── */
#hero{padding:5rem 0 3rem;text-align:center;position:relative}
.hero-eyebrow{
  display:inline-flex;align-items:center;gap:.5rem;
  font-size:.75rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;
  color:var(--a1);margin-bottom:1.25rem;
  background:rgba(124,58,237,.08);
  border:1px solid rgba(124,58,237,.2);
  padding:.4rem .9rem;border-radius:20px;
}
.hero-eyebrow .dot{width:5px;height:5px;background:var(--a1);border-radius:50%;box-shadow:0 0 12px var(--a1);animation:pulse 1.6s var(--ease) infinite}
.hero-title{
  font-size:clamp(2.2rem,5.8vw,3.8rem);
  font-weight:800;line-height:1.05;letter-spacing:-.04em;
  margin-bottom:1rem;
}
.hero-title .grad{
  background:var(--grad);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-size:200% auto;animation:shimmer 8s linear infinite;
}
@keyframes shimmer{to{background-position:200% center}}
.hero-sub{
  color:var(--muted);font-size:1.08rem;line-height:1.6;
  max-width:540px;margin:0 auto 2.5rem;
}

/* ── URL input ───────────────────────────────────────── */
.url-box{
  display:flex;gap:.5rem;
  max-width:680px;margin:0 auto;
  background:var(--surface);
  border:1.5px solid var(--border);
  border-radius:var(--r);
  padding:.5rem .5rem .5rem 1rem;
  box-shadow:var(--shadow);
  transition:all .25s var(--ease);
}
.url-box:hover{border-color:rgba(124,58,237,.4)}
.url-box:focus-within{border-color:var(--a1);box-shadow:var(--shadow-lift)}
.url-box .icon{display:flex;align-items:center;color:var(--muted);flex-shrink:0}
.url-box input{
  flex:1;background:none;border:none;outline:none;
  color:var(--text);font-size:1rem;font-family:inherit;
  padding:.7rem .25rem;min-width:0;
}
.url-box input::placeholder{color:var(--muted-2)}
.btn-go{
  position:relative;overflow:hidden;
  background:var(--grad);color:#fff;border:none;
  border-radius:var(--r-2);
  padding:.7rem 1.5rem;font-weight:700;font-size:.93rem;
  cursor:pointer;white-space:nowrap;
  transition:transform .15s var(--ease), box-shadow .25s var(--ease);
  display:flex;align-items:center;gap:.45rem;
  box-shadow:0 4px 16px rgba(124,58,237,.4), 0 1px 0 rgba(255,255,255,.15) inset;
}
.btn-go:hover{transform:translateY(-1px);box-shadow:0 8px 24px rgba(124,58,237,.55), 0 1px 0 rgba(255,255,255,.2) inset}
.btn-go:active{transform:translateY(0)}
.btn-go svg{width:14px;height:14px;transition:transform .25s var(--ease)}
.btn-go:hover svg{transform:translateX(2px)}

/* ── Pills ───────────────────────────────────────────── */
.pills{display:flex;justify-content:center;gap:.5rem;flex-wrap:wrap;margin-top:2rem}
.pill{
  display:inline-flex;align-items:center;gap:.4rem;
  background:var(--surface);border:1px solid var(--border-2);
  border-radius:24px;padding:.45rem 1rem;
  font-size:.78rem;color:var(--text-2);font-weight:500;
  transition:all .2s var(--ease);
}
.pill:hover{border-color:var(--border-3);color:var(--text);transform:translateY(-1px)}
.pill .ico{font-size:1rem}

/* ── Video info ──────────────────────────────────────── */
#video-info{padding:1.5rem 0 .5rem;animation:slideUp .4s var(--ease)}
@keyframes slideUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.video-card{
  display:flex;gap:1rem;align-items:center;
  background:var(--surface);border:1px solid var(--border-2);
  border-radius:var(--r);padding:.85rem 1rem;
  box-shadow:var(--shadow);
}
.video-thumb{
  width:100px;height:56px;border-radius:var(--r-3);
  object-fit:cover;flex-shrink:0;background:var(--surface-2);
  position:relative;
}
.video-meta{flex:1;min-width:0}
.video-meta h3{
  font-size:.95rem;font-weight:600;line-height:1.35;
  margin-bottom:.3rem;color:var(--text);
  overflow:hidden;text-overflow:ellipsis;display:-webkit-box;
  -webkit-line-clamp:2;-webkit-box-orient:vertical;
}
.video-id{
  font-size:.72rem;color:var(--muted);
  font-family:'JetBrains Mono',monospace;
  background:var(--surface-2);padding:.2rem .5rem;
  border-radius:4px;display:inline-block;
  border:1px solid var(--border-2);
}
.btn-new-video{
  flex-shrink:0;display:inline-flex;align-items:center;gap:.35rem;
  background:var(--surface-2);border:1px solid var(--border-2);
  color:var(--muted);
  border-radius:var(--r-3);padding:.5rem .85rem;
  font-size:.78rem;font-weight:600;
  cursor:pointer;font-family:inherit;
  transition:all .2s var(--ease);
}
.btn-new-video:hover{border-color:var(--a1);color:var(--text);background:rgba(124,58,237,.08)}

/* ── Tabs ────────────────────────────────────────────── */
#actions{padding:.5rem 0 1.5rem;animation:slideUp .4s var(--ease) .05s both}
.tabs{
  display:flex;gap:.3rem;
  background:var(--surface);
  border:1px solid var(--border-2);
  border-radius:var(--r-2);
  padding:.3rem;margin-bottom:1.2rem;
  box-shadow:var(--shadow);
}
.tab{
  flex:1;display:flex;align-items:center;justify-content:center;gap:.45rem;
  padding:.7rem 1rem;border:none;background:transparent;
  border-radius:var(--r-3);
  cursor:pointer;font-weight:600;font-size:.88rem;
  color:var(--muted);font-family:inherit;
  transition:all .2s var(--ease);
  position:relative;
}
.tab:hover{color:var(--text);background:rgba(255,255,255,.03)}
.tab.active{
  color:#fff;
  background:var(--grad);
  box-shadow:0 4px 12px rgba(124,58,237,.35), 0 1px 0 rgba(255,255,255,.15) inset;
}
.tab.has-result:not(.active)::after{
  content:'';
  position:absolute;top:.4rem;right:.7rem;
  width:7px;height:7px;border-radius:50%;
  background:var(--success);
  box-shadow:0 0 8px var(--success);
}
.tab-icon{font-size:1rem}

/* ── Options panel ───────────────────────────────────── */
.options-panel{
  background:var(--surface);
  border:1px solid var(--border-2);
  border-radius:var(--r);padding:1.4rem;
  box-shadow:var(--shadow);
  animation:fadeIn .3s var(--ease);
}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.opt-row{display:grid;grid-template-columns:1fr 1fr;gap:.85rem;margin-bottom:1rem}
.opt-row:last-of-type{margin-bottom:0}
.opt-group label{
  display:block;font-size:.7rem;font-weight:700;
  color:var(--muted);margin-bottom:.45rem;
  text-transform:uppercase;letter-spacing:.08em;
}
.opt-group select,
.opt-group input[type=number],
.opt-group input[type=text],
.opt-group input[type=password]{
  width:100%;background:var(--surface-2);
  border:1px solid var(--border-2);
  border-radius:var(--r-3);padding:.65rem .8rem;
  color:var(--text);font-size:.9rem;font-family:inherit;
  outline:none;transition:all .2s var(--ease);
}
.opt-group select:focus,
.opt-group input:focus{
  border-color:var(--a1);
  box-shadow:0 0 0 3px rgba(124,58,237,.15);
  background:var(--surface-3);
}
.opt-group select{
  appearance:none;-webkit-appearance:none;
  background-image:url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%237d7d95' stroke-width='2'%3e%3cpolyline points='6 9 12 15 18 9'/%3e%3c/svg%3e");
  background-repeat:no-repeat;background-position:right .7rem center;
  background-size:14px;padding-right:2rem;
}
.opt-group select option{background:var(--surface-2);color:var(--text)}

/* ── Source toggle ───────────────────────────────────── */
.src-toggle{
  display:flex;gap:.3rem;
  background:var(--surface-2);
  border:1px solid var(--border-2);
  border-radius:var(--r-3);padding:.3rem;
}
.src-btn{
  flex:1;background:transparent;border:none;
  color:var(--muted);padding:.6rem .8rem;
  border-radius:var(--r-4);
  font-weight:600;font-size:.85rem;cursor:pointer;
  font-family:inherit;
  transition:all .2s var(--ease);
}
.src-btn:hover{color:var(--text)}
.src-btn.active{background:var(--grad);color:#fff;box-shadow:0 2px 8px rgba(124,58,237,.4)}

/* ── File input ──────────────────────────────────────── */
#audio-file{
  display:block;width:100%;
  padding:.85rem;
  background:var(--surface-2);
  border:1.5px dashed rgba(124,58,237,.3);
  border-radius:var(--r-3);
  color:var(--text);font-family:inherit;font-size:.85rem;
  cursor:pointer;transition:all .2s var(--ease);
}
#audio-file:hover{border-color:var(--a1);background:var(--surface-3)}
#audio-file::file-selector-button{
  background:var(--grad);color:#fff;border:none;
  border-radius:var(--r-4);padding:.45rem .85rem;
  cursor:pointer;font-weight:600;margin-right:.7rem;
  font-family:inherit;font-size:.82rem;
  transition:transform .15s var(--ease);
}
#audio-file::file-selector-button:hover{transform:translateY(-1px)}

/* ── Info banner ─────────────────────────────────────── */
.info-banner{
  display:flex;gap:.7rem;align-items:flex-start;
  background:linear-gradient(135deg,rgba(124,58,237,.08),rgba(236,72,153,.05));
  border:1px solid rgba(124,58,237,.25);
  border-radius:var(--r-3);
  padding:.85rem 1rem;margin-bottom:1rem;
  font-size:.85rem;line-height:1.55;color:var(--text-2);
}
.info-banner .info-icon{font-size:1.1rem;flex-shrink:0;line-height:1.4}
.info-banner strong{color:var(--text);font-weight:700}

/* ── YouTube tool cards (grid) ───────────────────────── */
.yt-tools-row{
  display:grid;grid-template-columns:repeat(4,1fr);
  gap:.55rem;margin-bottom:1rem;
}
@media (max-width:600px){.yt-tools-row{grid-template-columns:repeat(2,1fr)}}
.yt-tool-card{
  display:flex;flex-direction:column;align-items:center;
  gap:.2rem;padding:.85rem .5rem;
  background:var(--surface-2);
  border:1px solid var(--border-2);
  border-radius:var(--r-3);
  text-decoration:none;
  transition:all .25s var(--ease);
  text-align:center;
}
.yt-tool-card:hover{
  border-color:var(--a1);
  transform:translateY(-2px);
  background:rgba(124,58,237,.06);
  box-shadow:0 6px 20px rgba(124,58,237,.15);
}
.yt-tool-icon{font-size:1.3rem;margin-bottom:.15rem}
.yt-tool-name{font-size:.85rem;font-weight:700;color:var(--text)}
.yt-tool-desc{font-size:.7rem;color:var(--muted)}

/* ── YouTube helper (legacy) ─────────────────────────── */
.yt-helper{
  margin:.6rem 0 1rem;
  background:var(--surface-2);
  border:1px solid var(--border-2);
  border-radius:var(--r-3);padding:.7rem .9rem;
}
.yt-helper summary{
  cursor:pointer;color:var(--a1);
  font-size:.85rem;font-weight:600;outline:none;
  display:flex;align-items:center;gap:.4rem;
  list-style:none;
}
.yt-helper summary::-webkit-details-marker{display:none}
.yt-helper summary::before{content:'▸';transition:transform .2s var(--ease);font-size:.7em}
.yt-helper[open] summary::before{transform:rotate(90deg)}
.yt-helper summary:hover{opacity:.8}
.yt-helper-body{padding:.7rem 0 .2rem}
.yt-helper-body p{
  font-size:.82rem;color:var(--muted);
  margin-bottom:.6rem;line-height:1.5;
}
.yt-tool{
  display:flex;align-items:center;justify-content:space-between;
  padding:.6rem .85rem;
  background:var(--surface);
  border:1px solid var(--border-2);
  border-radius:var(--r-4);
  margin-bottom:.4rem;
  text-decoration:none;color:var(--text);
  font-size:.85rem;font-weight:500;
  transition:all .2s var(--ease);
}
.yt-tool:hover{
  border-color:var(--a1);transform:translateX(3px);
  background:rgba(124,58,237,.05);
}
.yt-tool span{font-size:.72rem;color:var(--muted);font-weight:400}

/* ── Buttons ─────────────────────────────────────────── */
.btn-main{
  display:flex;align-items:center;justify-content:center;gap:.5rem;
  width:100%;padding:.95rem;
  background:var(--grad);color:#fff;border:none;
  border-radius:var(--r-3);
  font-weight:700;font-size:.95rem;
  cursor:pointer;font-family:inherit;
  transition:transform .15s var(--ease), box-shadow .25s var(--ease);
  box-shadow:0 4px 16px rgba(124,58,237,.35), 0 1px 0 rgba(255,255,255,.15) inset;
  margin-top:.7rem;
  letter-spacing:-.005em;
}
.btn-main:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 8px 24px rgba(124,58,237,.5), 0 1px 0 rgba(255,255,255,.2) inset}
.btn-main:active:not(:disabled){transform:translateY(0)}
.btn-main:disabled{opacity:.5;cursor:not-allowed}
.btn-secondary{
  display:inline-flex;align-items:center;gap:.4rem;
  background:var(--surface-2);
  border:1px solid var(--border-2);
  color:var(--text);
  border-radius:var(--r-3);
  padding:.6rem 1rem;
  font-weight:600;font-size:.85rem;
  cursor:pointer;font-family:inherit;text-decoration:none;
  transition:all .2s var(--ease);
}
.btn-secondary:hover{border-color:var(--a1);background:rgba(124,58,237,.08)}

.check-langs-btn{
  background:var(--surface-2);
  border:1px solid var(--border);
  color:var(--text);border-radius:var(--r-3);
  padding:.65rem 1rem;font-size:.85rem;font-weight:600;
  cursor:pointer;width:100%;
  transition:all .2s var(--ease);margin-bottom:.7rem;
  display:flex;align-items:center;justify-content:center;gap:.45rem;
  font-family:inherit;
}
.check-langs-btn:hover{background:rgba(124,58,237,.08);border-color:var(--a1)}
.check-langs-btn:disabled{opacity:.6;cursor:wait}

/* ── Language list ──────────────────────────────────── */
.lang-list{
  max-height:180px;overflow-y:auto;
  background:var(--surface-2);
  border:1px solid var(--border-2);
  border-radius:var(--r-3);
  margin-top:.4rem;
}
.lang-item{
  padding:.55rem .85rem;cursor:pointer;
  font-size:.88rem;
  display:flex;justify-content:space-between;align-items:center;
  transition:background .15s var(--ease);
  border-bottom:1px solid var(--border-2);
}
.lang-item:last-child{border-bottom:none}
.lang-item:hover{background:rgba(124,58,237,.08)}
.lang-item.selected{background:rgba(124,58,237,.15);color:var(--a1);font-weight:600}
.lang-badge{
  font-size:.7rem;background:var(--surface);color:var(--muted);
  padding:.15rem .5rem;border-radius:4px;
  border:1px solid var(--border-2);font-weight:500;
}

/* ── Processing ──────────────────────────────────────── */
#processing{padding:1.5rem 0;animation:slideUp .35s var(--ease)}
.proc-card{
  background:var(--surface);
  border:1px solid var(--border-2);
  border-radius:var(--r);padding:1.5rem;
  box-shadow:var(--shadow);
}
.proc-header{display:flex;align-items:center;gap:.75rem;margin-bottom:1rem}
.spinner{
  width:22px;height:22px;
  border:2.5px solid var(--surface-3);
  border-top-color:var(--a1);
  border-right-color:var(--a2);
  border-radius:50%;
  animation:spin .8s linear infinite;
  flex-shrink:0;
}
@keyframes spin{to{transform:rotate(360deg)}}
.proc-title{font-weight:700;font-size:1rem;color:var(--text)}
.proc-bar{
  height:3px;background:var(--surface-2);
  border-radius:2px;overflow:hidden;margin-bottom:1rem;
  position:relative;
}
.proc-bar::after{
  content:'';position:absolute;top:0;left:-30%;
  width:30%;height:100%;background:var(--grad);
  border-radius:2px;
  animation:slide-progress 1.4s var(--ease) infinite;
}
@keyframes slide-progress{to{left:100%}}
.log-box{
  background:var(--surface-2);
  border:1px solid var(--border-2);
  border-radius:var(--r-3);
  padding:.85rem 1rem;
  font-size:.8rem;
  font-family:'JetBrains Mono',monospace;
  color:var(--text-2);
  max-height:240px;overflow-y:auto;
  line-height:1.65;
}
.log-line{padding:.05rem 0;animation:fadeInLine .25s var(--ease)}
@keyframes fadeInLine{from{opacity:0;transform:translateX(-3px)}to{opacity:1;transform:translateX(0)}}
.log-line.err{color:var(--error)}
.log-line.ok{color:var(--success)}

/* ── Result ──────────────────────────────────────────── */
#result{padding:1.5rem 0 4rem;animation:slideUp .4s var(--ease)}
.result-card{
  background:var(--surface);
  border:1px solid var(--border-2);
  border-radius:var(--r);
  overflow:hidden;
  box-shadow:var(--shadow);
}
.result-card-header{
  padding:1rem 1.25rem;
  border-bottom:1px solid var(--border-2);
  display:flex;align-items:center;justify-content:space-between;
  flex-wrap:wrap;gap:.6rem;
}
.result-card-title{
  font-weight:700;font-size:1rem;
  display:flex;align-items:center;gap:.55rem;
  color:var(--text);
}
.result-icon-wrap{
  width:34px;height:34px;
  background:var(--grad-soft);
  border:1px solid rgba(124,58,237,.3);
  border-radius:var(--r-3);
  display:flex;align-items:center;justify-content:center;
  font-size:1.1rem;
}
.stats-bar{
  display:flex;flex-wrap:wrap;gap:1.2rem;
}
.stat{display:flex;align-items:center;gap:.4rem;font-size:.83rem}
.stat-val{
  font-weight:700;color:var(--text);
  font-family:'JetBrains Mono',monospace;
}
.stat-lbl{color:var(--muted)}

.result-body{
  padding:1.25rem;
  max-height:60vh;overflow-y:auto;
}
.content-preview{
  font-size:.85rem;color:var(--text-2);line-height:1.7;
  white-space:pre-wrap;word-break:break-word;
  font-family:'JetBrains Mono',monospace;
}
.content-preview.markdown{font-family:'Inter',sans-serif;font-size:.92rem}
.content-preview.markdown h1,
.content-preview.markdown h2,
.content-preview.markdown h3{margin:.8rem 0 .4rem;font-weight:700;color:var(--text)}
.content-preview.markdown h1{font-size:1.3rem}
.content-preview.markdown h2{font-size:1.1rem}
.content-preview.markdown h3{font-size:1rem}
.content-preview.markdown p{margin:.4rem 0}
.content-preview.markdown ul,.content-preview.markdown ol{padding-left:1.3rem;margin:.4rem 0}
.content-preview.markdown li{margin:.2rem 0}
.content-preview.markdown blockquote{
  border-left:3px solid var(--a1);
  padding:.3rem .8rem;margin:.5rem 0;
  background:rgba(124,58,237,.05);
  border-radius:0 var(--r-4) var(--r-4) 0;
}
.content-preview.markdown code{
  background:var(--surface-2);padding:.1rem .35rem;
  border-radius:4px;font-family:'JetBrains Mono',monospace;
  font-size:.85em;border:1px solid var(--border-2);
}
.content-preview.markdown table{
  border-collapse:collapse;width:100%;margin:.5rem 0;
  font-size:.85em;
}
.content-preview.markdown th,
.content-preview.markdown td{
  border:1px solid var(--border-2);
  padding:.4rem .6rem;text-align:left;
}
.content-preview.markdown th{background:var(--surface-2);font-weight:600}
.content-preview.markdown strong{color:var(--text);font-weight:600}
.content-preview.markdown a{color:var(--a1);text-decoration:none}
.content-preview.markdown a:hover{text-decoration:underline}
.content-preview.markdown hr{border:none;border-top:1px solid var(--border-2);margin:1rem 0}

.result-actions{
  padding:1rem 1.25rem;
  border-top:1px solid var(--border-2);
  display:flex;gap:.6rem;flex-wrap:wrap;
  background:var(--surface-2);
}
.btn-dl{
  display:inline-flex;align-items:center;gap:.4rem;
  background:var(--surface);
  border:1px solid var(--border-2);
  color:var(--text);
  border-radius:var(--r-3);
  padding:.55rem 1rem;
  font-size:.85rem;font-weight:600;
  cursor:pointer;text-decoration:none;font-family:inherit;
  transition:all .2s var(--ease);
}
.btn-dl:hover{border-color:var(--a1);background:rgba(124,58,237,.08);transform:translateY(-1px)}
.btn-chat{
  display:inline-flex;align-items:center;gap:.4rem;
  background:var(--grad);color:#fff;border:none;
  border-radius:var(--r-3);padding:.55rem 1.1rem;
  font-size:.85rem;font-weight:700;
  cursor:pointer;font-family:inherit;
  transition:all .2s var(--ease);
  box-shadow:0 4px 12px rgba(124,58,237,.35), 0 1px 0 rgba(255,255,255,.15) inset;
}
.btn-chat:hover{transform:translateY(-1px);box-shadow:0 6px 18px rgba(124,58,237,.5)}

.ai-link-box{
  background:rgba(16,185,129,.08);
  border:1px solid rgba(16,185,129,.25);
  border-radius:var(--r-3);
  padding:.8rem 1rem;margin-top:.9rem;
  font-size:.82rem;
}
.ai-link-label{
  color:var(--success);font-weight:700;
  margin-bottom:.35rem;
  display:flex;align-items:center;gap:.4rem;
}
.ai-link-url{
  color:var(--text);
  font-family:'JetBrains Mono',monospace;
  word-break:break-all;font-size:.78rem;
  display:flex;align-items:center;gap:.5rem;
}
.copy-btn{
  background:transparent;border:1px solid var(--border-2);
  color:var(--muted);
  border-radius:4px;padding:.2rem .55rem;
  font-size:.72rem;cursor:pointer;font-family:inherit;
  margin-left:auto;flex-shrink:0;
  transition:all .2s var(--ease);
}
.copy-btn:hover{border-color:var(--a1);color:var(--text)}

/* ── Chat drawer ─────────────────────────────────────── */
.chat-backdrop{
  position:fixed;inset:0;
  background:rgba(0,0,0,.5);
  backdrop-filter:blur(6px);
  -webkit-backdrop-filter:blur(6px);
  z-index:90;
  opacity:0;pointer-events:none;
  transition:opacity .3s var(--ease);
}
.chat-backdrop.open{opacity:1;pointer-events:all}
.chat-drawer{
  position:fixed;top:0;right:0;bottom:0;
  width:min(720px,100vw);
  background:linear-gradient(180deg,#0a0a18 0%,#0e0e1f 100%);
  border-left:1px solid var(--border-2);
  z-index:100;
  display:flex;flex-direction:column;
  transform:translateX(100%);
  transition:transform .4s var(--ease);
  box-shadow:-20px 0 60px rgba(0,0,0,.6);
}
.chat-drawer.open{transform:translateX(0)}
.chat-header{
  padding:1rem 1.25rem;
  border-bottom:1px solid var(--border-2);
  background:rgba(255,255,255,.02);
  flex-shrink:0;
  display:flex;align-items:center;justify-content:space-between;
  gap:.5rem;
}
.chat-title{
  font-weight:700;font-size:.95rem;
  display:flex;align-items:center;gap:.55rem;
}
.chat-controls{display:flex;align-items:center;gap:.55rem;flex-wrap:wrap}
.model-select{
  background:var(--surface-2);
  border:1px solid var(--border-2);
  border-radius:var(--r-4);
  color:var(--text);font-size:.78rem;
  padding:.4rem .65rem;outline:none;
  cursor:pointer;font-family:inherit;
  appearance:none;-webkit-appearance:none;
  background-image:url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%237d7d95' stroke-width='2'%3e%3cpolyline points='6 9 12 15 18 9'/%3e%3c/svg%3e");
  background-repeat:no-repeat;background-position:right .5rem center;
  background-size:12px;padding-right:1.7rem;
  transition:border-color .2s var(--ease);
}
.model-select:hover{border-color:var(--border-3)}
.think-toggle{
  display:flex;align-items:center;gap:.35rem;
  font-size:.75rem;color:var(--muted);cursor:pointer;
}
.think-toggle input{accent-color:var(--a1)}
.btn-close-drawer{
  background:transparent;border:none;
  color:var(--muted);cursor:pointer;
  width:32px;height:32px;border-radius:8px;
  display:flex;align-items:center;justify-content:center;
  font-size:1.3rem;
  transition:all .2s var(--ease);
  font-family:inherit;
}
.btn-close-drawer:hover{background:var(--surface-2);color:var(--text)}
.btn-clear{
  background:transparent;border:1px solid var(--border-2);
  color:var(--muted);
  border-radius:var(--r-4);padding:.3rem .65rem;
  font-size:.74rem;cursor:pointer;font-family:inherit;
  transition:all .2s var(--ease);
}
.btn-clear:hover{border-color:var(--error);color:var(--error)}

.chat-messages{
  flex:1;overflow-y:auto;
  padding:1.2rem 1.4rem 1rem;
  display:flex;flex-direction:column;gap:1.4rem;
  min-height:0;
  scroll-behavior:smooth;
}
.msg{
  display:flex;gap:.8rem;align-items:flex-start;
  max-width:100%;
  animation:msgIn .3s var(--ease);
}
@keyframes msgIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg-avatar{
  width:32px;height:32px;border-radius:50%;
  flex-shrink:0;
  display:flex;align-items:center;justify-content:center;
  font-size:.85rem;font-weight:700;
  background:var(--surface-3);
  border:1px solid var(--border-2);
}
.msg.user .msg-avatar{
  background:var(--grad);
  color:#fff;
  border-color:transparent;
  box-shadow:0 2px 8px rgba(124,58,237,.4);
}
.msg.assistant .msg-avatar{
  background:linear-gradient(135deg,#1e1e3f 0%,#2a2a4d 100%);
  color:var(--a1);
  border:1px solid rgba(124,58,237,.3);
}
.msg-content{
  flex:1;min-width:0;
  display:flex;flex-direction:column;gap:.3rem;
}
.msg-name{
  font-size:.78rem;font-weight:700;
  color:var(--text);
  display:flex;align-items:center;gap:.5rem;
}
.msg-name-tag{
  font-size:.65rem;font-weight:600;text-transform:uppercase;
  letter-spacing:.05em;color:var(--muted);
  padding:.1rem .4rem;background:var(--surface-2);
  border:1px solid var(--border-2);border-radius:4px;
}
.msg-bubble{
  padding:.1rem 0;
  font-size:.92rem;line-height:1.65;
  word-break:break-word;color:var(--text);
}
.msg.user .msg-bubble{
  background:var(--surface-2);
  border:1px solid var(--border-2);
  padding:.7rem .95rem;
  border-radius:var(--r-2);
  border-top-left-radius:4px;
}
.msg-bubble h1,.msg-bubble h2,.msg-bubble h3{
  font-size:1.05em;font-weight:700;
  margin:.7rem 0 .3rem;color:var(--text);
}
.msg-bubble h1:first-child,.msg-bubble h2:first-child,.msg-bubble h3:first-child{margin-top:0}
.msg-bubble h1{font-size:1.2em}
.msg-bubble p{margin:.4rem 0}
.msg-bubble p:first-child{margin-top:0}
.msg-bubble p:last-child{margin-bottom:0}
.msg-bubble ul,.msg-bubble ol{padding-left:1.4rem;margin:.4rem 0}
.msg-bubble li{margin:.25rem 0;line-height:1.6}
.msg-bubble li::marker{color:var(--a1)}
.msg-bubble code{
  background:rgba(124,58,237,.12);
  color:#e8d5ff;
  padding:.12rem .4rem;border-radius:4px;
  font-family:'JetBrains Mono',monospace;font-size:.85em;
  border:1px solid rgba(124,58,237,.2);
}
.msg-bubble pre{
  background:#080814;
  border:1px solid var(--border-2);
  border-radius:8px;padding:.85rem 1rem;
  overflow-x:auto;margin:.6rem 0;
  font-size:.85em;
}
.msg-bubble pre code{background:none;padding:0;border:none;color:#e2e8f0}
.msg-bubble blockquote{
  border-left:3px solid var(--a1);
  padding:.3rem .8rem;margin:.5rem 0;
  background:rgba(124,58,237,.06);
  border-radius:0 var(--r-4) var(--r-4) 0;
  color:var(--text-2);
}
.msg-bubble strong{color:var(--text);font-weight:700}
.msg-bubble a{color:var(--a3);text-decoration:underline;text-underline-offset:2px}
.msg-bubble hr{border:none;border-top:1px solid var(--border-2);margin:.7rem 0}
.msg-bubble table{border-collapse:collapse;margin:.5rem 0;font-size:.88em;width:100%}
.msg-bubble th,.msg-bubble td{border:1px solid var(--border-2);padding:.4rem .6rem;text-align:left}
.msg-bubble th{background:var(--surface-2);font-weight:600}
.msg-meta{font-size:.7rem;color:var(--muted-2);font-weight:500;margin-top:.15rem}

.typing-dots{display:inline-flex;gap:5px;padding:.4rem 0}
.typing-dots span{
  width:7px;height:7px;
  background:linear-gradient(135deg,var(--a1),var(--a2));
  border-radius:50%;
  animation:typing-pulse 1.2s var(--ease) infinite;
}
.typing-dots span:nth-child(2){animation-delay:.18s}
.typing-dots span:nth-child(3){animation-delay:.36s}
@keyframes typing-pulse{
  0%,60%,100%{transform:scale(.7);opacity:.4}
  30%{transform:scale(1);opacity:1}
}

.chat-input-area{
  padding:.85rem;
  border-top:1px solid var(--border-2);
  background:var(--surface);
  flex-shrink:0;
}
.upload-preview{display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:.5rem}
.upload-chip{
  display:flex;align-items:center;gap:.3rem;
  background:var(--surface-2);
  border:1px solid var(--border-2);
  border-radius:6px;padding:.25rem .55rem;
  font-size:.74rem;color:var(--text-2);
}
.upload-chip button{
  background:none;border:none;
  color:var(--muted);cursor:pointer;
  font-size:.95rem;line-height:1;padding:0 .15rem;
}
.chat-row{display:flex;gap:.45rem;align-items:flex-end}
.chat-input{
  flex:1;background:var(--surface-2);
  border:1.5px solid var(--border-2);
  border-radius:var(--r-3);
  padding:.7rem .9rem;
  color:var(--text);font-size:.92rem;font-family:inherit;
  outline:none;resize:none;max-height:120px;line-height:1.5;
  transition:border-color .2s var(--ease);
}
.chat-input:focus{border-color:var(--a1);box-shadow:0 0 0 3px rgba(124,58,237,.12)}
.chat-btns{display:flex;gap:.4rem;flex-shrink:0}
.btn-icon{
  background:var(--surface-2);
  border:1px solid var(--border-2);
  color:var(--muted);
  border-radius:var(--r-3);
  width:40px;height:40px;
  display:flex;align-items:center;justify-content:center;
  cursor:pointer;font-size:1rem;font-family:inherit;
  transition:all .2s var(--ease);
}
.btn-icon:hover{border-color:var(--a1);color:var(--text)}
.btn-send{
  background:var(--grad);color:#fff;border:none;
  border-radius:var(--r-3);
  width:40px;height:40px;
  display:flex;align-items:center;justify-content:center;
  cursor:pointer;
  transition:all .2s var(--ease);
  box-shadow:0 2px 8px rgba(124,58,237,.35);
}
.btn-send:hover:not(:disabled){transform:translateY(-1px);box-shadow:0 4px 12px rgba(124,58,237,.5)}
.btn-send:disabled{opacity:.4;cursor:not-allowed}

/* ── Empty state ─────────────────────────────────────── */
.chat-empty{
  flex:1;display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  color:var(--muted);gap:.7rem;padding:2rem 1.5rem;
  text-align:center;
}
.chat-empty-icon{
  font-size:2.5rem;opacity:.3;
  width:60px;height:60px;
  background:var(--grad-soft);
  border-radius:16px;
  display:flex;align-items:center;justify-content:center;
}
.chat-empty p{font-size:.9rem;color:var(--text-2);max-width:300px;line-height:1.5}
.tip-chips{
  display:flex;flex-wrap:wrap;gap:.45rem;
  justify-content:center;margin-top:.6rem;
}
.tip{
  background:var(--surface-2);
  border:1px solid var(--border-2);
  border-radius:20px;padding:.4rem .85rem;
  font-size:.78rem;cursor:pointer;
  color:var(--text-2);font-weight:500;
  transition:all .2s var(--ease);
}
.tip:hover{border-color:var(--a1);color:var(--text);transform:translateY(-1px)}

/* ── Toast ───────────────────────────────────────────── */
.toast{
  position:fixed;bottom:1.5rem;left:50%;
  transform:translateX(-50%) translateY(100px);
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:var(--r-2);
  padding:.7rem 1.1rem;
  font-size:.88rem;font-weight:500;
  z-index:200;
  box-shadow:0 12px 36px rgba(0,0,0,.5);
  transition:transform .3s var(--ease-bounce);
  display:flex;align-items:center;gap:.55rem;
  max-width:90vw;
}
.toast.show{transform:translateX(-50%) translateY(0)}
.toast.success{border-color:rgba(16,185,129,.4)}
.toast.error{border-color:rgba(239,68,68,.4)}

/* ── Mobile ──────────────────────────────────────────── */
@media (max-width:720px){
  #hero{padding:3rem 0 2rem}
  .hero-sub{margin-bottom:2rem}
  .url-box{flex-direction:column;padding:.6rem;border-radius:var(--r)}
  .url-box .icon{display:none}
  .url-box input{padding:.65rem .75rem}
  .btn-go{width:100%;justify-content:center;padding:.75rem}
  .opt-row{grid-template-columns:1fr}
  .tabs{flex-wrap:wrap}
  .tab{font-size:.8rem;padding:.6rem .5rem}
  .tab-icon{font-size:.95rem}
  .video-card{padding:.7rem}
  .video-thumb{width:80px;height:45px}
  .video-meta h3{font-size:.85rem}
  .stats-bar{gap:.7rem}
  .result-card-header{flex-direction:column;align-items:flex-start}
  .nav-badge{display:none}
  .chat-drawer{width:100vw}
  .chat-controls{gap:.35rem}
  .model-select{font-size:.72rem;padding:.32rem .55rem;padding-right:1.4rem}
}
</style>
</head>
<body>

<!-- Navbar -->
<nav>
  <div class="logo"><span class="logo-dot"></span>yt<span>bro</span></div>
  <div class="nav-right">
    <div class="nav-badge">Free · No Sign-up</div>
  </div>
</nav>

<div class="container">

<!-- Hero -->
<section id="hero">
  <div class="hero-eyebrow"><span class="dot"></span>Free · 99 Languages · No Sign-up</div>
  <h1 class="hero-title">Analyze YouTube<br/>with <span class="grad">AI</span></h1>
  <p class="hero-sub">Download comments, captions and AI transcripts — then chat with Claude, GPT-5 or Gemini about any video</p>

  <div class="url-box">
    <span class="icon">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
    </span>
    <input id="url-input" type="text" placeholder="Paste YouTube URL or video ID…" autocomplete="off" spellcheck="false"/>
    <button class="btn-go" id="btn-analyze" onclick="analyzeUrl()">
      <span>Analyze</span>
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 8h10M9 4l4 4-4 4"/></svg>
    </button>
  </div>

  <div class="pills">
    <div class="pill"><span class="ico">💬</span> Comments</div>
    <div class="pill"><span class="ico">📝</span> Captions</div>
    <div class="pill"><span class="ico">🎙️</span> AI Transcript</div>
    <div class="pill"><span class="ico">🤖</span> Chat with AI</div>
  </div>
</section>

<!-- Video info -->
<section id="video-info" class="hidden">
  <div class="video-card">
    <img id="vid-thumb" class="video-thumb" src="" alt=""/>
    <div class="video-meta">
      <h3 id="vid-title">Loading…</h3>
      <span id="vid-id" class="video-id"></span>
    </div>
    <button class="btn-new-video" onclick="clearSession()" title="Try a different video">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9"/><polyline points="3 4 3 12 11 12"/></svg>
      <span>New</span>
    </button>
  </div>
</section>

<!-- Action tabs -->
<section id="actions" class="hidden">
  <div class="tabs">
    <button class="tab active" id="tab-comments" onclick="switchTab('comments')">
      <span class="tab-icon">💬</span><span>Comments</span>
    </button>
    <button class="tab" id="tab-captions" onclick="switchTab('captions')">
      <span class="tab-icon">📝</span><span>Captions</span>
    </button>
    <button class="tab" id="tab-transcribe" onclick="switchTab('transcribe')">
      <span class="tab-icon">🎙️</span><span>Transcribe</span>
    </button>
  </div>

  <!-- Comments -->
  <div id="opt-comments" class="options-panel">
    <div class="opt-row">
      <div class="opt-group">
        <label>Sort By</label>
        <select id="sort-mode">
          <option value="recent">Most Recent</option>
          <option value="popular">Most Popular</option>
        </select>
      </div>
      <div class="opt-group">
        <label>Max Comments (0 = all)</label>
        <input type="number" id="max-comments" value="0" min="0" step="100"/>
      </div>
    </div>
    <button class="btn-main" onclick="startDownload('comments')">
      <span>⬇️</span> Download All Comments
    </button>
  </div>

  <!-- Captions -->
  <div id="opt-captions" class="options-panel hidden">
    <button class="check-langs-btn" onclick="checkLanguages()">
      <span>🔍</span> Check Available Languages
    </button>
    <div id="lang-list-wrap" class="hidden">
      <div class="opt-group">
        <label>Select Language</label>
        <div class="lang-list" id="lang-list"></div>
      </div>
    </div>
    <button class="btn-main" id="btn-dl-captions" onclick="startDownload('captions')">
      <span>⬇️</span> Download Captions
    </button>
  </div>

  <!-- Transcribe -->
  <div id="opt-transcribe" class="options-panel hidden">
    <div class="info-banner">
      <div class="info-icon">💡</div>
      <div>
        <strong>Step 1:</strong> Get the audio file from YouTube using any tool below (free). <strong>Step 2:</strong> Upload it here. <strong>Step 3:</strong> Generate transcript in any language — completely free.
      </div>
    </div>

    <div class="yt-tools-row">
      <a href="https://cobalt.tools" target="_blank" rel="noopener" class="yt-tool-card">
        <div class="yt-tool-icon">🟣</div>
        <div class="yt-tool-name">Cobalt.tools</div>
        <div class="yt-tool-desc">clean · no ads</div>
      </a>
      <a href="https://yt5s.io" target="_blank" rel="noopener" class="yt-tool-card">
        <div class="yt-tool-icon">🟢</div>
        <div class="yt-tool-name">YT5S.io</div>
        <div class="yt-tool-desc">fast MP3</div>
      </a>
      <a href="https://ytmp3.gg" target="_blank" rel="noopener" class="yt-tool-card">
        <div class="yt-tool-icon">🔵</div>
        <div class="yt-tool-name">YTMP3.gg</div>
        <div class="yt-tool-desc">simple</div>
      </a>
      <a href="https://9convert.com" target="_blank" rel="noopener" class="yt-tool-card">
        <div class="yt-tool-icon">🟠</div>
        <div class="yt-tool-name">9Convert</div>
        <div class="yt-tool-desc">alternative</div>
      </a>
    </div>

    <div class="opt-group" style="margin-bottom:.85rem">
      <label>Audio File</label>
      <input type="file" id="audio-file" accept="audio/*,video/*,.mp3,.wav,.m4a,.flac,.ogg,.webm,.mp4" onchange="onAudioFile(this)"/>
      <div id="audio-file-info" style="font-size:.78rem;color:var(--muted);margin-top:.5rem"></div>
    </div>

    <div class="opt-row">
      <div class="opt-group">
        <label>Engine</label>
        <select id="trans-engine" onchange="onEngineChange()">
          <option value="browser">🌐 Browser Whisper · free · 99 langs</option>
          <option value="groq">⚡ Groq Cloud · faster · needs key</option>
        </select>
      </div>
      <div class="opt-group">
        <label id="trans-model-label">Model</label>
        <select id="trans-model">
          <option value="Xenova/whisper-tiny">Tiny — fastest · 75MB</option>
          <option value="Xenova/whisper-base" selected>Base — balanced · 150MB</option>
          <option value="Xenova/whisper-small">Small — accurate · 480MB</option>
        </select>
      </div>
    </div>
    <div id="groq-key-row" class="opt-row hidden" style="grid-template-columns:1fr">
      <div class="opt-group">
        <label>Groq API Key <a href="https://console.groq.com/keys" target="_blank" rel="noopener" style="color:var(--a1);font-size:.7rem;text-decoration:none">get free key →</a></label>
        <input type="password" id="groq-key" placeholder="gsk_…" oninput="saveGroqKey(this.value)"/>
      </div>
    </div>
    <button class="btn-main" onclick="startTranscribe()">
      <span>🎙️</span> Generate Transcript
    </button>
  </div>
</section>

<!-- Processing -->
<section id="processing" class="hidden">
  <div class="proc-card">
    <div class="proc-header">
      <div class="spinner"></div>
      <div class="proc-title" id="proc-title">Processing…</div>
    </div>
    <div class="proc-bar"></div>
    <div class="log-box" id="log-box"></div>
  </div>
</section>

<!-- Result -->
<section id="result" class="hidden">
  <div class="result-card">
    <div class="result-card-header">
      <div class="result-card-title">
        <div class="result-icon-wrap"><span id="result-icon">📄</span></div>
        <span id="result-label">Content</span>
      </div>
      <div id="result-stats" class="stats-bar"></div>
    </div>
    <div class="result-body">
      <div class="content-preview markdown" id="content-preview"></div>
      <div id="ai-link-box" class="ai-link-box hidden">
        <div class="ai-link-label">🤖 AI-Readable Link</div>
        <div class="ai-link-url">
          <span id="ai-link-url"></span>
          <button class="copy-btn" onclick="copyAiLink()">Copy</button>
        </div>
      </div>
    </div>
    <div class="result-actions">
      <a id="btn-download" class="btn-dl" href="#" download>
        <span>⬇️</span> Download .md
      </a>
      <button class="btn-dl" onclick="copyContent()">
        <span>📋</span> Copy
      </button>
      <button class="btn-chat" onclick="openChat()" style="margin-left:auto">
        <span>🤖</span> Analyze with AI
      </button>
    </div>
  </div>
</section>

</div><!-- /container -->

<!-- Chat drawer -->
<div class="chat-backdrop" id="chat-backdrop" onclick="closeChat()"></div>
<aside class="chat-drawer" id="chat-drawer" aria-label="AI Chat">
  <div class="chat-header">
    <div class="chat-title">
      <div class="result-icon-wrap" style="width:30px;height:30px;font-size:.95rem">🤖</div>
      <span>AI Chat</span>
    </div>
    <div class="chat-controls">
      <select class="model-select" id="chat-model">
        <option value="claude">Claude Sonnet</option>
        <option value="claude-opus">Claude Opus</option>
        <option value="gpt-5.4">GPT-5.4</option>
        <option value="gemini">Gemini</option>
        <option value="sonar-pro">Sonar Pro</option>
        <option value="sonar">Sonar</option>
        <option value="r1">DeepSeek R1</option>
        <option value="reasoning">Reasoning</option>
        <option value="deep-research">Deep Research</option>
      </select>
      <label class="think-toggle">
        <input type="checkbox" id="thinking-toggle"/> Think
      </label>
      <button class="btn-clear" onclick="clearChat()">Clear</button>
      <button class="btn-close-drawer" onclick="closeChat()" aria-label="Close chat">×</button>
    </div>
  </div>
  <div class="chat-messages" id="chat-messages">
    <div class="chat-empty" id="chat-empty">
      <div class="chat-empty-icon">🤖</div>
      <p>Click <strong>Analyze with AI</strong> on the result to chat about your content</p>
      <div class="tip-chips">
        <div class="tip" onclick="sendTip(this)">Summarize this</div>
        <div class="tip" onclick="sendTip(this)">Key themes?</div>
        <div class="tip" onclick="sendTip(this)">Sentiment?</div>
        <div class="tip" onclick="sendTip(this)">Top comments</div>
      </div>
    </div>
  </div>
  <input type="file" id="file-upload" multiple accept="image/*,.pdf,.txt,.md,.csv" style="display:none" onchange="handleFiles(this)"/>
  <div class="chat-input-area">
    <div class="upload-preview" id="upload-preview"></div>
    <div class="chat-row">
      <textarea class="chat-input" id="chat-input" rows="1" placeholder="Ask anything about the content…" onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
      <div class="chat-btns">
        <button class="btn-icon" onclick="document.getElementById('file-upload').click()" title="Attach file">📎</button>
        <button class="btn-send" id="btn-send" onclick="sendMessage()" title="Send">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2L2 8l4 2 2 4 6-12z"/></svg>
        </button>
      </div>
    </div>
  </div>
</aside>

<!-- Toast -->
<div class="toast" id="toast"><span id="toast-msg"></span></div>

<script>
// ── Config ────────────────────────────────────────────
const BACKEND = 'https://redstdui-ytbro-api.hf.space';
const AI_API  = 'https://ytbro.redstudio2595.workers.dev/aiproxy';

let state = {
  videoId:'', videoUrl:'', videoTitle:'', videoThumb:'',
  currentTab:'comments', selectedLang:null,
  results:{},               // {comments:{...}, captions:{...}, transcribe:{...}}
  chatHistory:[], uploadedFiles:[], contextLoaded:false,
  audioFile:null,
  whisperPipeline:null, whisperModelId:null,
};

// ── Persistence (localStorage) ───────────────────────
const STORAGE_KEY = 'ytbro_session_v1';
function saveSession(){
  try {
    const s = {
      videoId: state.videoId, videoUrl: state.videoUrl,
      videoTitle: state.videoTitle, videoThumb: state.videoThumb,
      currentTab: state.currentTab,
      selectedLang: state.selectedLang,
      results: state.results,
      chatHistory: state.chatHistory,
      contextLoaded: state.contextLoaded,
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch(e){}
}
function restoreSession(){
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return false;
    const s = JSON.parse(raw);
    if (!s.videoId) return false;
    state.videoId = s.videoId;
    state.videoUrl = s.videoUrl;
    state.videoTitle = s.videoTitle || s.videoId;
    state.videoThumb = s.videoThumb || \`https://img.youtube.com/vi/\${s.videoId}/hqdefault.jpg\`;
    state.currentTab = s.currentTab || 'comments';
    state.selectedLang = s.selectedLang;
    state.results = s.results || {};
    state.chatHistory = s.chatHistory || [];
    state.contextLoaded = s.contextLoaded || false;

    document.getElementById('url-input').value = state.videoUrl;
    document.getElementById('vid-thumb').src = state.videoThumb;
    document.getElementById('vid-title').textContent = state.videoTitle;
    document.getElementById('vid-id').textContent = state.videoId;
    setHero(false);
    show('video-info'); show('actions');
    switchTab(state.currentTab);
    if (state.results[state.currentTab]) showResult(state.currentTab, false);

    // Restore chat history (skip system messages, show user/assistant pairs)
    if (state.chatHistory && state.chatHistory.length > 1) {
      const empty = document.getElementById('chat-empty');
      if (empty) empty.remove();
      for (const m of state.chatHistory) {
        if (m.role === 'system') continue;
        const text = typeof m.content === 'string' ? m.content
          : (Array.isArray(m.content) ? m.content.find(p=>p.type==='text')?.text || '' : '');
        if (text) appendMsg(m.role, text);
      }
    }
    return true;
  } catch(e) { console.warn('restoreSession failed', e); return false; }
}
function clearSession(){
  try { localStorage.removeItem(STORAGE_KEY); } catch(e){}
  state.videoId=''; state.videoUrl=''; state.videoTitle=''; state.videoThumb='';
  state.results={}; state.chatHistory=[]; state.contextLoaded=false; state.selectedLang=null;
  hide('video-info'); hide('actions'); hide('result'); hide('processing');
  document.getElementById('url-input').value='';
  setHero(true);
}

document.addEventListener('DOMContentLoaded', () => {
  const saved = localStorage.getItem('groq_key');
  if (saved) document.getElementById('groq-key').value = saved;
  document.getElementById('url-input').addEventListener('keydown', e => { if (e.key === 'Enter') analyzeUrl(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeChat(); });
  restoreSession();
});

// ── Toast ─────────────────────────────────────────────
function toast(msg, type=''){
  const t = document.getElementById('toast');
  document.getElementById('toast-msg').textContent = msg;
  t.className = 'toast show' + (type ? ' '+type : '');
  setTimeout(() => t.classList.remove('show'), 2600);
}

// ── URL analyze ───────────────────────────────────────
function extractVideoId(input){
  const s = input.trim();
  // Direct 11-char ID
  if (/^[\\w-]{11}$/.test(s)) return s;
  // URL patterns
  const patterns = [
    /youtube\\.com\\/watch\\?v=([\\w-]{11})/,
    /youtu\\.be\\/([\\w-]{11})/,
    /youtube\\.com\\/embed\\/([\\w-]{11})/,
    /youtube\\.com\\/shorts\\/([\\w-]{11})/,
    /youtube\\.com\\/live\\/([\\w-]{11})/,
  ];
  for (const p of patterns) {
    const m = s.match(p);
    if (m) return m[1];
  }
  return null;
}

async function analyzeUrl(){
  const url = document.getElementById('url-input').value.trim();
  if (!url) { toast('Paste a YouTube URL first', 'error'); return; }

  const vid = extractVideoId(url);
  if (!vid) { toast('Not a valid YouTube video URL', 'error'); return; }

  // If same video, don't reset
  if (state.videoId === vid) { switchTab(state.currentTab); return; }

  // New video → reset session
  state.videoId = vid;
  state.videoUrl = \`https://www.youtube.com/watch?v=\${vid}\`;
  state.videoThumb = \`https://img.youtube.com/vi/\${vid}/hqdefault.jpg\`;
  state.videoTitle = 'Loading…';
  state.results = {};
  state.chatHistory = [];
  state.contextLoaded = false;
  state.selectedLang = null;

  setHero(false);
  show('video-info');
  document.getElementById('vid-thumb').src = state.videoThumb;
  document.getElementById('vid-title').textContent = state.videoTitle;
  document.getElementById('vid-id').textContent = state.videoId;
  show('actions');
  switchTab('comments');
  hide('result'); hide('processing');

  // Fetch real title via noembed.com (CORS-enabled, uses browser residential IP)
  fetchVideoTitle(vid).then(title => {
    if (title) {
      state.videoTitle = title;
      document.getElementById('vid-title').textContent = title;
      saveSession();
    }
  });
  saveSession();
}

async function fetchVideoTitle(vid){
  // Try noembed.com first (CORS-enabled YouTube oembed proxy)
  try {
    const r = await fetch(\`https://noembed.com/embed?url=https://www.youtube.com/watch?v=\${vid}\`);
    const d = await r.json();
    if (d.title) return d.title;
  } catch(e){}
  // Fallback: backend
  try {
    const r = await fetch(\`\${BACKEND}/api/video/info\`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url:\`https://www.youtube.com/watch?v=\${vid}\`}),
    });
    const d = await r.json();
    if (d.title && d.title !== vid) return d.title;
  } catch(e){}
  return null;
}

function switchTab(tab){
  state.currentTab = tab;
  ['comments','captions','transcribe'].forEach(t => {
    const tabEl = document.getElementById(\`tab-\${t}\`);
    tabEl.classList.toggle('active', t === tab);
    tabEl.classList.toggle('has-result', !!state.results[t]);
    document.getElementById(\`opt-\${t}\`).classList.toggle('hidden', t !== tab);
  });
  hide('processing');
  if (state.results[tab]) showResult(tab, false);
  else hide('result');
  saveSession();
}

// ── Captions language check ───────────────────────────
async function checkLanguages(){
  const btn = document.querySelector('.check-langs-btn');
  btn.innerHTML = '<span>⏳</span> Checking…';
  btn.disabled = true;
  try {
    const res = await fetch(\`\${BACKEND}/api/captions/languages\`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url: state.videoUrl}),
    });
    const data = await res.json();
    const list = document.getElementById('lang-list');
    list.innerHTML = '';
    [...(data.manual||[]).map(l => ({...l, type:'manual'})),
     ...(data.auto||[]).map(l => ({...l, type:'auto'}))]
      .forEach(lang => {
        const div = document.createElement('div');
        div.className = 'lang-item';
        div.innerHTML = \`<span>\${lang.name}</span><span class="lang-badge">\${lang.type}</span>\`;
        div.onclick = () => {
          document.querySelectorAll('.lang-item').forEach(el => el.classList.remove('selected'));
          div.classList.add('selected');
          state.selectedLang = {code: lang.code, name: lang.name};
        };
        list.appendChild(div);
      });
    show('lang-list-wrap');
    btn.innerHTML = '<span>✅</span> Languages loaded';
  } catch (e) {
    btn.innerHTML = '<span>❌</span> Failed — retry';
    btn.disabled = false;
  }
}

// ── Transcribe controls ──────────────────────────────
function onAudioFile(input){
  const f = input.files[0];
  if (!f) { state.audioFile = null; document.getElementById('audio-file-info').textContent = ''; return; }
  state.audioFile = f;
  const mb = (f.size/1048576).toFixed(1);
  document.getElementById('audio-file-info').textContent = \`📎 \${f.name} · \${mb} MB · \${f.type || 'audio'}\`;
}
function onEngineChange(){
  const eng = document.getElementById('trans-engine').value;
  const groqRow = document.getElementById('groq-key-row');
  const lbl = document.getElementById('trans-model-label');
  const sel = document.getElementById('trans-model');
  if (eng === 'groq') {
    groqRow.classList.remove('hidden');
    lbl.textContent = 'Groq Model';
    sel.innerHTML = \`
      <option value="whisper-large-v3">whisper-large-v3 (best · 99 langs)</option>
      <option value="whisper-large-v3-turbo">whisper-large-v3-turbo (fast)</option>\`;
  } else {
    groqRow.classList.add('hidden');
    lbl.textContent = 'Browser Model';
    sel.innerHTML = \`
      <option value="Xenova/whisper-tiny">Tiny — fastest · 75MB</option>
      <option value="Xenova/whisper-base" selected>Base — balanced · 150MB</option>
      <option value="Xenova/whisper-small">Small — accurate · 480MB</option>\`;
  }
}

async function startTranscribe(){
  const engine = document.getElementById('trans-engine').value;
  const model = document.getElementById('trans-model').value;
  if (!state.audioFile) { toast('Choose an audio file first', 'error'); return; }

  show('processing'); hide('result');
  state._currentDownload = null;
  // Don't clear chat — let user keep chatting about previous results
  const log = document.getElementById('log-box'); log.innerHTML = '';
  document.getElementById('proc-title').textContent = '🎙️ Generating transcript…';
  document.querySelector('.spinner').style.display = '';

  try {
    if (engine === 'browser') await transcribeWithBrowserWhisper(model, log);
    else await transcribeWithGroq(model, log);
    if (state._currentDownload) {
      state.results['transcribe'] = state._currentDownload;
      saveSession();
    }
    showResult('transcribe');
  } catch (err) {
    addLog(log, '❌ ' + (err.message||err), 'err');
    document.getElementById('proc-title').textContent = '❌ Transcription failed';
    document.querySelector('.spinner').style.display = 'none';
  }
}

// ── Browser Whisper ──────────────────────────────────
async function transcribeWithBrowserWhisper(modelId, log){
  addLog(log, 'Loading Transformers.js…');
  const tf = await import('https://cdn.jsdelivr.net/npm/@xenova/transformers@2.17.2');
  tf.env.allowLocalModels = false;
  tf.env.useBrowserCache = true;

  const blob = state.audioFile;
  addLog(log, \`Using uploaded file: \${state.audioFile.name}\`);

  addLog(log, 'Decoding audio…');
  const arrayBuf = await blob.arrayBuffer();
  const audioCtx = new (window.AudioContext||window.webkitAudioContext)({sampleRate: 16000});
  let decoded;
  try { decoded = await audioCtx.decodeAudioData(arrayBuf); }
  catch(e){ throw new Error('Could not decode audio. Try MP3, WAV, M4A or OGG.'); }
  let mono;
  if (decoded.numberOfChannels === 1) mono = decoded.getChannelData(0);
  else {
    const a = decoded.getChannelData(0), b = decoded.getChannelData(1);
    mono = new Float32Array(a.length);
    for (let i = 0; i < a.length; i++) mono[i] = (a[i]+b[i])/2;
  }
  const durSec = mono.length/16000;
  addLog(log, \`Audio: \${Math.floor(durSec/60)}m\${Math.floor(durSec%60)}s · 16kHz mono\`);

  if (state.whisperModelId !== modelId) {
    addLog(log, \`Loading model \${modelId} (downloads first time, then cached)…\`);
    state.whisperPipeline = await tf.pipeline('automatic-speech-recognition', modelId, {
      progress_callback: (p) => {
        if (p.status === 'progress' && p.progress) {
          const pct = p.progress.toFixed(0);
          const lines = log.querySelectorAll('.log-line');
          const last = lines[lines.length-1];
          if (last && last.dataset.kind === 'progress') {
            last.textContent = \`> Downloading \${p.file||'model'}: \${pct}%\`;
          } else {
            const d = document.createElement('div');
            d.className = 'log-line'; d.dataset.kind = 'progress';
            d.textContent = \`> Downloading \${p.file||'model'}: \${pct}%\`;
            log.appendChild(d); log.scrollTop = log.scrollHeight;
          }
        }
      },
    });
    state.whisperModelId = modelId;
    addLog(log, 'Model loaded ✓', 'ok');
  }

  addLog(log, 'Transcribing…');
  const result = await state.whisperPipeline(mono, {
    return_timestamps: true,
    chunk_length_s: 30,
    stride_length_s: 5,
  });

  const text = result.text || '';
  const lang = result.language || 'auto';
  const wordCount = text.split(/\\s+/).filter(Boolean).length;
  const title = state.audioFile.name.replace(/\\.[^.]+$/, '');

  let md = \`# Transcript: \${title}\\n\\n- **Engine:** Browser Whisper (\${modelId})\\n- **Language:** \${lang}\\n- **Words:** \${wordCount.toLocaleString()}\\n- **Duration:** \${Math.floor(durSec/60)}m\${Math.floor(durSec%60)}s\\n\\n---\\n\\n\`;
  if (result.chunks && result.chunks.length) {
    for (const c of result.chunks) {
      const t = c.timestamp && c.timestamp[0] != null ? formatTs(c.timestamp[0]) : '';
      md += t ? \`**[\${t}]** \${c.text.trim()}\\n\\n\` : \`\${c.text.trim()}\\n\\n\`;
    }
  } else md += text;

  state._currentDownload = {
    type:'result', content: md, title,
    filename: \`transcript_\${title.replace(/[^a-zA-Z0-9]/g,'_').slice(0,40)}.md\`,
    stats: { words: wordCount, language: lang, duration: \`\${Math.floor(durSec/60)}m\${Math.floor(durSec%60)}s\` },
  };
  addLog(log, \`Done! \${wordCount.toLocaleString()} words · language: \${lang}\`, 'ok');
}

function formatTs(s){
  s = Math.floor(s||0);
  const m = Math.floor(s/60), ss = String(s%60).padStart(2,'0');
  return \`\${String(m).padStart(2,'0')}:\${ss}\`;
}

// ── Groq cloud (file upload) ─────────────────────────
async function transcribeWithGroq(model, log){
  const apiKey = document.getElementById('groq-key').value.trim();
  if (!apiKey) throw new Error('Enter a Groq API key first.');

  const sizeMB = state.audioFile.size / 1048576;
  if (sizeMB > 25) throw new Error(\`File too large (\${sizeMB.toFixed(1)}MB). Groq max is 25MB. Switch to Browser Whisper for unlimited size.\`);

  addLog(log, \`Uploading \${state.audioFile.name} (\${sizeMB.toFixed(1)}MB) to Groq…\`);
  const form = new FormData();
  form.append('file', state.audioFile);
  form.append('api_key', apiKey);
  form.append('model', model);
  const res = await fetch(\`\${BACKEND}/api/transcribe/file\`, { method:'POST', body: form });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(\`Upload failed: \${err.substring(0,200)}\`);
  }
  await readSSE(res, log);
}

async function readSSE(res, log){
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buf += dec.decode(value, {stream:true});
    const lines = buf.split('\\n');
    buf = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const evt = JSON.parse(line.slice(6));
        if (evt.type === 'progress') addLog(log, evt.message);
        else if (evt.type === 'result') { state._currentDownload = evt; addLog(log, '✅ Done!', 'ok'); }
        else if (evt.type === 'error') { addLog(log, '❌ ' + evt.message, 'err'); throw new Error(evt.message); }
        else if (evt.type === 'done') return;
      } catch(e) { if (e.message) throw e; }
    }
  }
}

// ── Comments / Captions ──────────────────────────────
async function startDownload(type){
  show('processing'); hide('result');
  state._currentDownload = null;
  const log = document.getElementById('log-box'); log.innerHTML = '';
  document.querySelector('.spinner').style.display = '';

  const titles = {comments:'💬 Downloading comments…', captions:'📝 Downloading captions…'};
  document.getElementById('proc-title').textContent = titles[type];

  let endpoint, body;
  if (type === 'comments') {
    endpoint = '/api/comments';
    body = {url: state.videoUrl, sort: document.getElementById('sort-mode').value, max_comments: parseInt(document.getElementById('max-comments').value)||0};
  } else if (type === 'captions') {
    if (!state.selectedLang) { toast('Select a language first', 'error'); hide('processing'); return; }
    endpoint = '/api/captions/download';
    body = {url: state.videoUrl, lang_code: state.selectedLang.code, lang_name: state.selectedLang.name};
  }

  try {
    const res = await fetch(\`\${BACKEND}\${endpoint}\`, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
    await readSSE(res, log);
    if (state._currentDownload) {
      state.results[type] = state._currentDownload;
      saveSession();
    }
    showResult(type);
  } catch (err) {
    addLog(log, '❌ ' + err.message, 'err');
    document.getElementById('proc-title').textContent = '❌ Download failed';
    document.querySelector('.spinner').style.display = 'none';
  }
}

function addLog(box, msg, cls=''){
  const div = document.createElement('div');
  div.className = 'log-line' + (cls ? ' ' + cls : '');
  div.textContent = '> ' + msg;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

// ── Result view ──────────────────────────────────────
function showResult(type, fromAction=true){
  const result = state.results[type];
  if (!result) {
    if (fromAction) {
      document.getElementById('proc-title').textContent = '❌ Failed — see log above';
      document.querySelector('.spinner').style.display = 'none';
    }
    hide('result');
    return;
  }
  hide('processing'); show('result');

  const icons = {comments:'💬', captions:'📝', transcribe:'🎙️'};
  const labels = {comments:'Comments', captions:'Captions', transcribe:'Transcript'};
  document.getElementById('result-icon').textContent = icons[type];
  document.getElementById('result-label').textContent = labels[type];

  const s = result.stats || {};
  let html = '';
  if (s.total)    html += \`<span class="stat"><span class="stat-val">\${s.total.toLocaleString()}</span><span class="stat-lbl">comments</span></span>\`;
  if (s.words)    html += \`<span class="stat"><span class="stat-val">\${s.words.toLocaleString()}</span><span class="stat-lbl">words</span></span>\`;
  if (s.duration) html += \`<span class="stat"><span class="stat-val">\${s.duration}</span><span class="stat-lbl">duration</span></span>\`;
  if (s.language) html += \`<span class="stat"><span class="stat-val">\${s.language}</span><span class="stat-lbl">lang</span></span>\`;
  document.getElementById('result-stats').innerHTML = html;

  const content = result.content || '';
  const preview = document.getElementById('content-preview');
  preview.innerHTML = marked.parse(content.substring(0, 8000) + (content.length > 8000 ? '\\n\\n_…truncated_' : ''));

  if (result.ai_url) {
    document.getElementById('ai-link-url').textContent = result.ai_url;
    show('ai-link-box');
  } else hide('ai-link-box');

  const blob = new Blob([content], {type:'text/markdown'});
  const dl = document.getElementById('btn-download');
  dl.href = URL.createObjectURL(blob);
  dl.download = result.filename || 'content.md';
}

function getCurrentResult(){ return state.results[state.currentTab]; }
function copyContent(){
  const r = getCurrentResult();
  navigator.clipboard.writeText(r?.content || '');
  toast('✅ Copied to clipboard', 'success');
}
function copyAiLink(){
  navigator.clipboard.writeText(document.getElementById('ai-link-url').textContent);
  toast('✅ Link copied', 'success');
}

// ── Chat drawer ──────────────────────────────────────
function openChat(){
  document.getElementById('chat-backdrop').classList.add('open');
  document.getElementById('chat-drawer').classList.add('open');
  document.body.style.overflow = 'hidden';
  const result = getCurrentResult();
  if (result && !state.contextLoaded) {
    state.contextLoaded = true;
    const title = state.videoTitle || result.title || 'this content';
    const fullContent = result.content || '';
    // Send up to 200,000 chars (~50k tokens — fits in Claude Sonnet 200k, GPT-5 128k, Gemini 1M)
    // For 837 comments at ~100 chars each = ~84k chars, full set fits
    const MAX_CTX = 200000;
    const content = fullContent.length > MAX_CTX
      ? fullContent.substring(0, MAX_CTX) + \`\\n\\n[TRUNCATED at \${MAX_CTX} chars — total content is \${fullContent.length} chars]\`
      : fullContent;
    state.chatHistory = [{
      role:'system',
      content: \`You are analyzing YouTube content from the video titled "\${title}".\\nContent type: \${state.currentTab}.\\nFull content (\${fullContent.length === content.length ? 'COMPLETE' : 'partial'}):\\n\\n\${content}\\n\\nBe direct, insightful, and use markdown formatting. When the user asks about a specific user/comment, search the entire content carefully before saying it doesn't exist.\`
    }];
    const empty = document.getElementById('chat-empty');
    if (empty) empty.remove();
    const sizeMsg = fullContent.length > MAX_CTX ? \` _(\${(fullContent.length/1000).toFixed(0)}K chars, sent \${(MAX_CTX/1000).toFixed(0)}K to AI)_\` : '';
    appendMsg('assistant', \`I've loaded the **\${state.currentTab}** for **"\${title}"**\${sizeMsg}.\\n\\nAsk me anything — summary, key themes, sentiment, specific users/comments, translations…\`);
    saveSession();
  }
  setTimeout(() => document.getElementById('chat-input').focus(), 350);
}
function closeChat(){
  document.getElementById('chat-backdrop').classList.remove('open');
  document.getElementById('chat-drawer').classList.remove('open');
  document.body.style.overflow = '';
}
function sendTip(el){ openChat(); document.getElementById('chat-input').value = el.textContent; sendMessage(); }

async function sendMessage(){
  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text && state.uploadedFiles.length === 0) return;

  const btn = document.getElementById('btn-send');
  btn.disabled = true;
  input.value = ''; input.style.height = 'auto';

  let content;
  if (state.uploadedFiles.length > 0) {
    content = [{type:'text', text}];
    state.uploadedFiles.forEach(f => {
      if (f.dataUri.startsWith('data:image')) content.push({type:'image_url', image_url:{url:f.dataUri}});
    });
  } else content = text;

  appendMsg('user', text, state.uploadedFiles.map(f => f.name));
  state.uploadedFiles = []; document.getElementById('upload-preview').innerHTML = '';
  state.chatHistory.push({role:'user', content});

  const model = document.getElementById('chat-model').value;
  const thinking = document.getElementById('thinking-toggle').checked;

  const msgs = document.getElementById('chat-messages');
  const {wrap, bubble} = buildMsg('assistant', model);
  bubble.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
  msgs.appendChild(wrap);
  msgs.scrollTop = msgs.scrollHeight;

  try {
    const res = await fetch(AI_API, {
      method:'POST',
      headers:{'Content-Type':'application/json','Accept':'text/event-stream'},
      body: JSON.stringify({model, thinking, messages: state.chatHistory, stream:true}),
    });
    if (!res.ok) {
      bubble.textContent = \`❌ Server returned \${res.status}. Try a different model.\`;
      btn.disabled = false; return;
    }
    let acc = '';
    const ct = (res.headers.get('Content-Type')||'').toLowerCase();
    if (ct.includes('event-stream') || ct.includes('text/plain')) {
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buf += dec.decode(value, {stream:true});
        const lines = buf.split('\\n');
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          const data = line.slice(5).trim();
          if (!data || data === '[DONE]') continue;
          try {
            const j = JSON.parse(data);
            const delta = j.choices?.[0]?.delta?.content || j.choices?.[0]?.message?.content || j.delta || j.content || '';
            if (delta) {
              acc += delta;
              bubble.innerHTML = marked.parse(acc);
              msgs.scrollTop = msgs.scrollHeight;
            }
          } catch {}
        }
      }
    } else {
      const data = await res.json();
      acc = data.choices?.[0]?.message?.content || data.content || '(No response)';
      bubble.innerHTML = marked.parse(acc);
    }
    if (!acc.trim()) bubble.textContent = '(No response — try again or switch model)';
    state.chatHistory.push({role:'assistant', content: acc});
    saveSession();
  } catch (err) {
    bubble.textContent = \`❌ Error: \${err.message}\`;
  }
  btn.disabled = false;
  document.getElementById('chat-input').focus();
}

const MODEL_NAMES = {
  'claude':'Claude Sonnet','claude-opus':'Claude Opus','gpt-5.4':'GPT-5.4',
  'gemini':'Gemini','sonar-pro':'Sonar Pro','sonar':'Sonar',
  'r1':'DeepSeek R1','reasoning':'Reasoning','deep-research':'Deep Research',
};
function buildMsg(role, modelKey){
  const wrap = document.createElement('div');
  wrap.className = \`msg \${role}\`;
  const avatar = document.createElement('div');
  avatar.className = 'msg-avatar';
  avatar.textContent = role === 'user' ? '🧑' : '🤖';
  const content = document.createElement('div'); content.className = 'msg-content';
  const name = document.createElement('div'); name.className = 'msg-name';
  if (role === 'user') name.textContent = 'You';
  else {
    name.innerHTML = \`<span>\${MODEL_NAMES[modelKey]||modelKey}</span><span class="msg-name-tag">AI</span>\`;
  }
  const bubble = document.createElement('div'); bubble.className = 'msg-bubble';
  content.appendChild(name); content.appendChild(bubble);
  wrap.appendChild(avatar); wrap.appendChild(content);
  return {wrap, bubble};
}
function appendMsg(role, text, fileNames=[]){
  const msgs = document.getElementById('chat-messages');
  const empty = document.getElementById('chat-empty');
  if (empty) empty.remove();
  const modelKey = document.getElementById('chat-model').value;
  const {wrap, bubble} = buildMsg(role, modelKey);
  if (role === 'assistant') bubble.innerHTML = marked.parse(text);
  else {
    bubble.textContent = text;
    if (fileNames.length) {
      fileNames.forEach(n => {
        const c = document.createElement('div');
        c.style.cssText = 'font-size:.72rem;opacity:.75;margin-top:.3rem';
        c.textContent = '📎 ' + n;
        bubble.appendChild(c);
      });
    }
  }
  msgs.appendChild(wrap);
  msgs.scrollTop = msgs.scrollHeight;
}

function handleFiles(input){
  const preview = document.getElementById('upload-preview');
  Array.from(input.files).forEach(file => {
    const reader = new FileReader();
    reader.onload = e => {
      state.uploadedFiles.push({name: file.name, dataUri: e.target.result});
      const chip = document.createElement('div');
      chip.className = 'upload-chip';
      chip.innerHTML = \`📎 \${file.name} <button onclick="removeFile('\${file.name}',this.parentElement)">×</button>\`;
      preview.appendChild(chip);
    };
    reader.readAsDataURL(file);
  });
  input.value = '';
}
function removeFile(name, el){
  state.uploadedFiles = state.uploadedFiles.filter(f => f.name !== name);
  el.remove();
}
function clearChat(){
  state.chatHistory = []; state.contextLoaded = false;
  document.getElementById('chat-messages').innerHTML = \`
    <div class="chat-empty" id="chat-empty">
      <div class="chat-empty-icon">🤖</div>
      <p>Click <strong>Analyze with AI</strong> on the result to chat about your content</p>
      <div class="tip-chips">
        <div class="tip" onclick="sendTip(this)">Summarize this</div>
        <div class="tip" onclick="sendTip(this)">Key themes?</div>
        <div class="tip" onclick="sendTip(this)">Sentiment?</div>
        <div class="tip" onclick="sendTip(this)">Top comments</div>
      </div>
    </div>\`;
}
function handleKey(e){ if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }
function autoResize(el){ el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px'; }
function saveGroqKey(val){ localStorage.setItem('groq_key', val); }
function show(id){ document.getElementById(id).classList.remove('hidden'); }
function hide(id){ document.getElementById(id).classList.add('hidden'); }
function setHero(visible){
  const el = document.getElementById('hero');
  el.style.paddingTop = visible ? '5rem' : '1.5rem';
  el.style.paddingBottom = visible ? '3rem' : '1rem';
  el.querySelector('.hero-eyebrow').style.display = visible ? '' : 'none';
  el.querySelector('.hero-title').style.display = visible ? '' : 'none';
  el.querySelector('.hero-sub').style.display = visible ? '' : 'none';
  el.querySelector('.pills').style.display = visible ? '' : 'none';
}
</script>
</body>
</html>`;
