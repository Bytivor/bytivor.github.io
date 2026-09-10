// Build-artifact integrity: no missing local links, images, scripts or styles.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../dist');
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]);
const pages = walk(root).filter(f => f.endsWith('.html'));
const errors = new Set();
for (const f of pages) {
  const html = fs.readFileSync(f, 'utf8');
  if (!/<title>[^<]+<\/title>/.test(html)) errors.add(`${f}: missing title`);
  for (const m of html.matchAll(/(?:href|src)=["']([^"']+)["']/g)) {
    const url = m[1];
    if (!url || url[0] === '#' || /^(?:[a-z]+:|\/\/)/i.test(url)) continue;
    let pathname;
    try { pathname = decodeURIComponent(url.split(/[?#]/)[0]); } catch { errors.add('Invalid URL: '+url); continue; }
    const target = pathname.startsWith('/') ? path.join(root, pathname) : path.resolve(path.dirname(f), pathname);
    if (!fs.existsSync(target) || (fs.statSync(target).isDirectory() && !fs.existsSync(path.join(target, 'index.html')))) errors.add(`${path.relative(root,f)} → ${url}`);
  }
}
for (const route of ['index.html','archives/index.html','tags/index.html','categories/index.html','portfolio/index.html','link/index.html','404.html']) {
  if (!fs.existsSync(path.join(root, route))) errors.add('Missing route: '+route);
}
if (errors.size) { console.error([...errors].join('\n')); process.exit(1); }
console.log(`${pages.length} HTML pages verified: all local links and asset references resolve.`);
