// Cloudflare Pages Function — injects per-link Open Graph tags so shared
// ?n=<node> and ?p=<from>,<to> links unfurl with a custom title/description.
// (Runs at the edge, before the scraper sees the HTML — which is why share
//  links use ?query, not #hash: fragments never reach the server.)

const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
const esc = s => String(s).replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

function bfsHops(data, a, b) {
  const adj = new Map();
  for (const l of data.links) {
    if (!l.album) continue;
    const s = l.source, t = l.target;
    (adj.get(s) || adj.set(s, []).get(s)).push(t);
    (adj.get(t) || adj.set(t, []).get(t)).push(s);
  }
  const seen = new Set([a]), q = [[a, 0]];
  while (q.length) {
    const [cur, d] = q.shift();
    if (cur === b) return d;
    for (const nb of (adj.get(cur) || [])) if (!seen.has(nb)) { seen.add(nb); q.push([nb, d + 1]); }
  }
  return null;
}

export async function onRequest(context) {
  const { request, env, next } = context;
  const url = new URL(request.url);
  const n = url.searchParams.get("n");
  const p = url.searchParams.get("p");

  const res = await next();
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("text/html") || (!n && !p)) return res;   // only HTML with a share param

  let data;
  try { data = await (await env.ASSETS.fetch(new URL("/data.json", url))).json(); }
  catch (e) { return res; }
  const bySlug = {};
  for (const nd of data.nodes) bySlug[slug(nd.id)] = nd;

  let title, desc;
  if (p) {
    const [a, b] = p.split(",");
    const A = bySlug[a], B = bySlug[b];
    if (!A || !B) return res;
    const hops = bfsHops(data, A.id, B.id);
    title = `${A.id} → ${B.id} · 2″`;
    desc = hops != null
      ? `A ${hops}-hop path through the indie recording network — who connects them, and how.`
      : `A path through the indie recording network.`;
  } else {
    const N = bySlug[n];
    if (!N) return res;
    const c = data.links.filter(l => l.album && (l.source === N.id || l.target === N.id)).length;
    const kind = N.type === "engineer" ? "engineer / producer" : N.type === "studio" ? "studio" : "artist / band";
    title = `${N.id} · 2″`;
    desc = `${N.id} — ${kind}${c ? `, ${c} credit${c === 1 ? "" : "s"}` : ""} in the indie recording network, 1995–2003.`;
  }

  const ogImg = esc(new URL("/og?" + (p ? "p=" + encodeURIComponent(p) : "n=" + encodeURIComponent(n)), url).toString());
  const T = esc(title), D = esc(desc), U = esc(url.toString());
  const html = (await res.text())
    .replace(/(<title>)[^<]*(<\/title>)/, `$1${T}$2`)
    .replace(/(<meta property="og:title" content=")[^"]*(")/, `$1${T}$2`)
    .replace(/(<meta property="og:description" content=")[^"]*(")/, `$1${D}$2`)
    .replace(/(<meta property="og:url" content=")[^"]*(")/, `$1${U}$2`)
    .replace(/(<meta property="og:image" content=")[^"]*(")/, `$1${ogImg}$2`)
    .replace(/(<meta property="og:image:secure_url" content=")[^"]*(")/, `$1${ogImg}$2`)
    .replace(/(<meta name="twitter:title" content=")[^"]*(")/, `$1${T}$2`)
    .replace(/(<meta name="twitter:description" content=")[^"]*(")/, `$1${D}$2`)
    .replace(/(<meta name="twitter:image" content=")[^"]*(")/, `$1${ogImg}$2`)
    .replace(/(<meta name="description" content=")[^"]*(")/, `$1${D}$2`);

  return new Response(html, { status: res.status, headers: { "content-type": "text/html; charset=utf-8" } });
}
