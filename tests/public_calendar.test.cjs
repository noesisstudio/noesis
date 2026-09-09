/* Contrato del iframe: consentimiento, emisor, altura y revocación. Sin red. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function element() {
  return { hidden: false, style: {}, children: [], listeners: {},
    addEventListener(name, fn) { this.listeners[name] = fn; },
    append(child) { this.children.push(child); },
    replaceChildren() { this.children = []; },
    focus() { this.focused = true; },
  };
}
const nodes = Object.fromEntries(['consent', 'mount', 'status', 'revoke', 'allow']
  .map(name => ['[data-cal-' + name + ']', element()]));
const root = { dataset: { calUrl: 'https://cal.com/bynoesis/agenda-una-llamada-con-nosotros' },
  querySelector: selector => nodes[selector] };
const events = [], messages = [], windowListeners = {};
const document = {
  querySelector: () => root,
  createElement: () => Object.assign(element(), {
    contentWindow: { postMessage: (payload, origin) => messages.push({ payload, origin }) },
  }),
  dispatchEvent: e => events.push(e.detail.name),
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../src/noesis/web/static/public-calendar.js'), 'utf8'), {
  document, window: { addEventListener: (name, fn) => { windowListeners[name] = fn; } },
  URL, CustomEvent: class { constructor(name, options) { this.detail = options.detail; } },
  setTimeout: () => 1, clearTimeout: () => {},
});
assert.equal(nodes['[data-cal-mount]'].children.length, 0, 'No conexión antes del permiso');
nodes['[data-cal-allow]'].listeners.click();
const iframe = nodes['[data-cal-mount]'].children[0];
assert.match(iframe.src, /^https:\/\/cal\.com\/bynoesis\/agenda-una-llamada-con-nosotros\/embed\?/);
nodes['[data-cal-allow]'].listeners.click();
assert.equal(nodes['[data-cal-mount]'].children.length, 1, 'El doble clic no crea dos calendarios');
assert.deepEqual(events, ['cal_demo_started']);
const send = (type, data = {}, origin = 'https://cal.com', source = iframe.contentWindow) =>
  windowListeners.message({ origin, source, data: { originator: 'CAL', fullType: 'CAL:noesis:' + type, data } });
send('bookingSuccessfulV2', {}, 'https://evil.example');
send('bookingSuccessfulV2', {}, 'https://cal.com', {});
assert.deepEqual(events, ['cal_demo_started'], 'No aceptar reservas de otra ventana u origen');
send('__iframeReady');
assert.equal(messages.length, 2);
assert.ok(messages.every(m => m.origin === 'https://cal.com'));
send('__dimensionChanged', { iframeHeight: 999999 });
assert.equal(iframe.style.height, '2400px');
send('__dimensionChanged', { iframeHeight: 'not-a-number' });
assert.equal(iframe.style.height, '2400px');
send('bookingSuccessfulV2', { email: 'private@example.com', uid: 'private' });
assert.deepEqual(events, ['cal_demo_started', 'cal_demo_booked'], 'Solo sale el nombre del evento');
nodes['[data-cal-revoke]'].listeners.click();
assert.equal(nodes['[data-cal-mount]'].children.length, 0);
assert.equal(nodes['[data-cal-consent]'].hidden, false);
send('bookingSuccessfulV2');
assert.equal(events.length, 2, 'No aceptar mensajes después de revocar');
console.log('OK: calendario sin red antes de consentir, origen/ventana, tamaño y revocación.');
