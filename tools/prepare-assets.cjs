const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const copy = (src, dest) => {
  const target = path.join(root, 'source/vendor', dest);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(path.join(root, 'node_modules', src), target);
};
copy('@fortawesome/fontawesome-free/css/all.min.css', 'fontawesome/css/all.min.css');
for (const file of fs.readdirSync(path.join(root, 'node_modules/@fortawesome/fontawesome-free/webfonts'))) {
  copy('@fortawesome/fontawesome-free/webfonts/' + file, 'fontawesome/webfonts/' + file);
}
copy('@fortawesome/fontawesome-free/LICENSE.txt', 'fontawesome/LICENSE.txt');
copy('medium-zoom/dist/medium-zoom.min.js', 'medium-zoom/medium-zoom.min.js');
copy('medium-zoom/LICENSE', 'medium-zoom/LICENSE.txt');
console.log('Local theme assets ready.');
