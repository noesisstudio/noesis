/* Vídeo de /bienvenida: YouTube solo se conecta al pulsar «Ver el vídeo».
 * Antes no hay ninguna petición a YouTube ni a Google. Se usa
 * youtube-nocookie.com, el único origen que la CSP permite en esa página.
 */
(function () {
  'use strict';
  const root = document.querySelector('[data-welcome-video]');
  if (!root) return;
  const id = root.dataset.videoId || '';
  const play = root.querySelector('[data-video-play]');
  const consent = root.querySelector('[data-video-consent]');
  const mount = root.querySelector('[data-video-mount]');
  if (!play || !consent || !mount || !/^[A-Za-z0-9_-]{11}$/.test(id)) return;
  play.addEventListener('click', () => {
    if (mount.firstChild) return;
    const url = new URL('https://www.youtube-nocookie.com/embed/' + id);
    url.searchParams.set('autoplay', '1');
    url.searchParams.set('rel', '0');
    url.searchParams.set('playsinline', '1');
    const iframe = document.createElement('iframe');
    iframe.title = 'Vídeo: cómo empezar con Bynoesis';
    iframe.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    iframe.allowFullscreen = true;
    // YouTube no reproduce incrustados que llegan sin origen de referencia.
    iframe.referrerPolicy = 'strict-origin-when-cross-origin';
    iframe.src = url.href;
    mount.append(iframe);
    consent.hidden = true;
    iframe.focus();
  });
}());
