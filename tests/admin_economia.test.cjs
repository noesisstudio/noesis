const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

test('abrir conserva supuestos; mover solo envía esa palanca; restaurar limpia cambios', async () => {
  const requests = [];
  const listeners = {};
  const reset = { addEventListener: (_, fn) => { listeners.reset = fn; } };
  const lever = {
    dataset: { ecoLever: 'retirada' }, value: '3000', min: '0', max: '3000',
    getAttribute: () => '7100.25',
    addEventListener: (_, fn) => { listeners.input = fn; },
  };
  const root = { dataset: {} };
  const document = {
    querySelector: selector => selector === '[data-eco-root]' ? root
      : selector === '[data-eco-reset]' ? reset : null,
    querySelectorAll: selector => selector === '[data-eco-lever]' ? [lever] : [],
  };
  const source = fs.readFileSync(path.join(__dirname, '../src/noesis/web/static/admin-economia.js'), 'utf8');
  vm.runInNewContext(source, {
    document, window: { location: { search: '' } }, Intl, URLSearchParams,
    clearTimeout() {}, setTimeout(fn) { fn(); return 1; },
    fetch: async url => {
      requests.push(url);
      return { ok: true, json: async () => ({ equilibrios: [], cabe_en_horas: {}, rampa: {} }) };
    },
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(lever.value, '7100.25');
  assert.equal(lever.max, 7100.25);
  assert.equal(requests[0], '/admin/economia/datos?');
  lever.value = '1500';
  listeners.input();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests[1], '/admin/economia/datos?retirada=1500');
  listeners.reset();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(lever.value, '7100.25');
  assert.equal(requests[2], '/admin/economia/datos?');
});
