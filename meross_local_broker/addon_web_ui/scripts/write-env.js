const fs = require('fs');
const path = require('path');

const pkg = require('../package.json');
const target = path.join(__dirname, '..', 'src', 'environments', '.env.ts');
const content = [
  'export const env: { [s: string]: (string | null); } = {',
  `  'npm_package_version': ${JSON.stringify(pkg.version)}`,
  '};',
  '',
].join('\n');

fs.writeFileSync(target, content, 'utf8');
console.log(`Wrote ${target}`);
