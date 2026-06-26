import { ImageResponse } from 'workers-og';

const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
const safe = s => String(s).replace(/[<>]/g, "");   // satori renders text literally — don't HTML-escape
const COLOR = { engineer: "#b23a2b", studio: "#b8862a", artist: "#3c5f78" };

function bfs(data, a, b) {
  const adj = new Map();
  for (const l of data.links) {
    if (!l.album) continue;
    (adj.get(l.source) || adj.set(l.source, []).get(l.source)).push(l.target);
    (adj.get(l.target) || adj.set(l.target, []).get(l.target)).push(l.source);
  }
  const prev = { [a]: null }, q = [a];
  while (q.length) {
    const cur = q.shift();
    if (cur === b) break;
    for (const nb of (adj.get(cur) || [])) if (!(nb in prev)) { prev[nb] = cur; q.push(nb); }
  }
  if (!(b in prev)) return null;
  const path = []; for (let c = b; c !== null; c = prev[c]) path.unshift(c);
  return path;
}

const frame = inner => `<div style="display:flex;width:1200px;height:630px;background:#e7e0cf;padding:46px;font-family:sans-serif;">
  <div style="display:flex;flex-direction:column;width:1108px;height:538px;border:3px solid #1b1a16;padding:38px 46px;">${inner}</div></div>`;

const header = `<div style="display:flex;justify-content:space-between;align-items:center;width:100%;">
  <div style="display:flex;font-size:44px;color:#a8432c;border:5px solid #a8432c;padding:2px 18px 12px;">2″</div>
  <div style="display:flex;font-size:22px;color:#6c6657;">2INCH.FM</div></div>`;

export async function onRequest(context) {
  const { env, request } = context;
  const url = new URL(request.url);
  const n = url.searchParams.get("n"), p = url.searchParams.get("p");
  let data;
  try { data = await (await env.ASSETS.fetch(new URL("/data.json", url))).json(); }
  catch (e) { return new Response("no data", { status: 500 }); }
  const bySlug = {}; data.nodes.forEach(nd => bySlug[slug(nd.id)] = nd);
  const byId = {}; data.nodes.forEach(nd => byId[nd.id] = nd);

  let inner;
  if (p) {
    const [a, b] = p.split(",");
    const A = bySlug[a], B = bySlug[b];
    if (!A || !B) return new Response("not found", { status: 404 });
    const path = bfs(data, A.id, B.id) || [A.id, B.id];
    const chips = path.map((id, i) => {
      const c = COLOR[(byId[id] || {}).type] || "#3c5f78";
      return `<div style="display:flex;align-items:center;margin:0 4px 12px 0;">
        <div style="display:flex;border:3px solid ${c};color:#1b1a16;font-size:24px;padding:4px 12px;">${safe(id)}</div>
        ${i < path.length - 1 ? `<div style="display:flex;color:#a8432c;font-size:26px;padding:0 6px;">→</div>` : ""}
      </div>`;
    }).join("");
    inner = `${header}<div style="display:flex;flex:1;"></div>
      <div style="display:flex;font-size:30px;color:#6c6657;margin-bottom:14px;">${path.length - 1}-hop path · six degrees</div>
      <div style="display:flex;flex-wrap:wrap;align-items:center;">${chips}</div>`;
  } else {
    const N = bySlug[n];
    if (!N) return new Response("not found", { status: 404 });
    const creds = data.links.filter(l => l.album && (l.source === N.id || l.target === N.id));
    const kind = N.type === "engineer" ? "Engineer / Producer" : N.type === "studio" ? "Studio" : "Artist / Band";
    const dots = creds.slice(0, 30).map(l => {
      const o = byId[l.source === N.id ? l.target : l.source] || {};
      return `<div style="display:flex;width:20px;height:20px;border-radius:10px;background:${COLOR[o.type] || "#3c5f78"};margin:0 7px 7px 0;"></div>`;
    }).join("");
    const name = N.id.length > 22 ? 64 : 84;
    inner = `${header}<div style="display:flex;flex:1;"></div>
      <div style="display:flex;font-size:26px;color:#6c6657;">${kind}</div>
      <div style="display:flex;font-size:${name}px;color:#1b1a16;">${safe(N.id)}</div>
      <div style="display:flex;font-size:30px;color:#a8432c;margin-top:12px;">${creds.length} credit${creds.length === 1 ? "" : "s"} · 1995–2003</div>
      <div style="display:flex;flex-wrap:wrap;margin-top:20px;">${dots}</div>`;
  }
  return new ImageResponse(frame(inner), { width: 1200, height: 630 });
}
