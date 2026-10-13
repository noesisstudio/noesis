/* El panel trabaja con días locales: una fecha pasada por UTC cambia de día en España. */
process.env.TZ = 'Europe/Madrid';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const web = path.join(__dirname, '..', 'src', 'noesis', 'web');
const appJs = fs.readFileSync(path.join(web, 'static', 'app.js'), 'utf8');
const source = appJs.match(/const localDate = [\s\S]*?;\n/);

test('localDate devuelve el día local, también a medianoche', () => {
  assert.ok(source, 'falta localDate en app.js');
  const localDate = vm.runInNewContext(`${source[0]} localDate`);
  const medianoche = new Date(2026, 9, 12);
  // El motivo de la función: en horario español UTC todavía es el día anterior.
  assert.equal(medianoche.toISOString().slice(0, 10), '2026-10-11');
  assert.equal(localDate(medianoche), '2026-10-12');
  assert.equal(localDate(new Date(2026, 0, 1, 0, 30)), '2026-01-01');
  assert.equal(localDate(new Date(2026, 11, 31, 23, 59)), '2026-12-31');
});

test('ninguna pantalla calcula el día con toISOString', () => {
  const dir = path.join(web, 'templates');
  const files = fs.readdirSync(dir, { recursive: true })
    .filter(name => name.endsWith('.html'));
  const culpables = files.filter(name => /toISOString\(\)\s*\.slice\(0,\s*10\)/
    .test(fs.readFileSync(path.join(dir, name), 'utf8')));
  assert.deepEqual(culpables, []);
});
