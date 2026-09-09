/* Ejecuta la animación y los contadores reales con DOM/reloj aislados. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function node() {
  const classes = new Set();
  return { dataset: {}, hidden: false, listeners: {}, attributes: {}, textContent: '',
    classList: { add: name => classes.add(name), toggle(name, on) {
      if (on) classes.add(name); else classes.delete(name);
    }, contains: name => classes.has(name) },
    addEventListener(name, fn) { this.listeners[name] = fn; },
    setAttribute(name, value) { this.attributes[name] = value; }, focus() {},
  };
}
function setup(reduced = false, pathname = '/') {
  const cases = [0, 1, 2].map(() => {
    const item = node();
    item.steps = [0, 1, 2, 3].map(n => Object.assign(node(), { dataset: { chatStep: n } }));
    item.querySelectorAll = () => item.steps;
    return item;
  });
  const buttons = [node(), node(), node()], pause = node(), open = node();
  const dialog = { showModal() { this.open = true; } };
  const demo = node();
  demo.querySelectorAll = selector => selector === '[data-chat-case]' ? cases : buttons;
  demo.querySelector = selector => ({ '[data-chat-pause]': pause,
    '[data-invoice-open]': open, dialog })[selector];
  const document = Object.assign(node(), { hidden: false,
    querySelector: () => null,
    querySelectorAll: selector => selector === '[data-conversation-demo]' ? [demo] : [],
  });
  const motion = { matches: reduced, addEventListener() {} };
  const sent = [], frames = [];
  let observer;
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../src/noesis/web/static/public-marketing.js'), 'utf8'), {
    document, window: { IntersectionObserver: true }, location: { pathname },
    matchMedia: () => motion,
    requestAnimationFrame: fn => { frames.push(fn); return frames.length; },
    IntersectionObserver: class { constructor(fn) { observer = fn; } observe() {} },
    fetch: (url, options) => { sent.push({url, options, payload: JSON.parse(options.body)}); return Promise.resolve(); },
  });
  let now = 0;
  return { cases, buttons, pause, open, dialog, document, sent, frames, demo,
    visibility(on) { observer([{ isIntersecting: on }]); },
    advance(count) { for (let i = 0; i < count && frames.length; i++) frames.shift()(now += 100); },
  };
}
const normal = setup();
assert.equal(normal.sent[0].payload.event, 'hero_demo_started');
normal.advance(25);
assert.ok(normal.cases[0].steps[3].classList.contains('is-visible'));
normal.advance(215);
assert.equal(normal.sent.filter(s => s.payload.event === 'hero_demo_completed').length, 1);
normal.advance(240);
assert.equal(normal.sent.filter(s => s.payload.event === 'hero_demo_completed').length, 1);
normal.visibility(false); normal.advance(2);
assert.equal(normal.frames.length, 0, 'No animar fuera de pantalla');
normal.visibility(true);
assert.equal(normal.frames.length, 1);
normal.buttons[1].listeners.click(); normal.advance(2);
assert.equal(normal.cases[1].hidden, false);
assert.equal(normal.pause.textContent, 'Reproducir');
assert.equal(normal.frames.length, 0, 'El caso manual queda estático');
normal.open.listeners.click(); assert.equal(normal.dialog.open, true);
for (const event of normal.sent) {
  assert.deepEqual(Object.keys(event.payload).sort(), ['event', 'page']);
  assert.equal(event.options.credentials, 'omit');
}
const quiet = setup(true);
assert.equal(quiet.frames.length, 0, 'Reduced motion sin autoplay');
assert.ok(quiet.cases[0].steps[3].classList.contains('is-visible'));
assert.equal(quiet.sent.length, 0);
quiet.pause.listeners.click(); quiet.advance(30);
assert.equal(quiet.sent.length, 1, 'Reproducción por petición explícita');
const other = setup(false, '/equipo');
other.advance(250);
assert.equal(other.sent.length, 0, 'No enviar rutas fuera de la lista pública');
console.log('OK: secuencia, pausa, visibilidad, reduced motion, modal y métricas mínimas.');
