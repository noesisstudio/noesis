import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const sharp = require("sharp");

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const repo = path.resolve(root, "..");
const sourceDir = path.join(root, "sources");
const fontPath = path.join(repo, "src", "noesis", "web", "static", "fonts", "fraunces-latin.woff2");
const fontData = fs.readFileSync(fontPath).toString("base64");

const C = {
  forest: "#14463B",
  teal: "#2E8B74",
  cream: "#F4F1E8",
  ink: "#15211C",
  sage: "#E4EFE9",
  warm: "#FAF8F3",
  deep: "#102820",
  muted: "#5D6B66",
  lightTeal: "#9FD6BD",
};

const assets = [];
const ensure = (p) => fs.mkdirSync(p, { recursive: true });
const esc = (value) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const fontFace = `@font-face{font-family:NoesisFraunces;src:url(data:font/woff2;base64,${fontData}) format('woff2');font-weight:400 700;font-style:normal}`;

function mark({ outer = C.teal, inner = C.forest, center = C.forest, dot = C.cream } = {}) {
  return `<g>
    <polygon points="32,3 38,26 61,32 38,38 32,61 26,38 3,32 26,26" fill="${outer}"/>
    <polygon points="32,13 36,28 51,32 36,36 32,51 28,36 13,32 28,28" fill="${inner}"/>
    <circle cx="32" cy="32" r="6.5" fill="${center}"/>
    <circle cx="32" cy="32" r="3.4" fill="${dot}"/>
  </g>`;
}

function svgDoc(width, height, body, label = "Noesis") {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(label)}">
    <style>${fontFace}</style>${body}</svg>`;
}

function logoSvg({ reverse = false, monochrome = false, wordmarkOnly = false } = {}) {
  const text = reverse ? C.cream : C.forest;
  const symbol = reverse
    ? mark({ outer: C.lightTeal, inner: C.cream, center: C.cream, dot: C.deep })
    : monochrome
      ? mark({ outer: C.forest, inner: C.forest, center: C.forest, dot: C.cream })
      : mark();
  return svgDoc(640, 180, `
    ${wordmarkOnly ? "" : `<g transform="translate(18 18) scale(2.25)">${symbol}</g>`}
    <text x="${wordmarkOnly ? 24 : 184}" y="128" fill="${text}" font-family="NoesisFraunces, Georgia, serif" font-size="104" font-weight="560" letter-spacing="-3">Noesis</text>
  `, "Noesis");
}

function logoPlate(width, height, background, reverse = false) {
  const symbol = reverse
    ? mark({ outer: C.lightTeal, inner: C.cream, center: C.cream, dot: C.deep })
    : mark();
  const text = reverse ? C.cream : C.forest;
  const icon = Math.round(height * 0.52);
  const totalWidth = icon + Math.round(height * 0.12) + Math.round(height * 1.45);
  const start = Math.round((width - totalWidth) / 2);
  const top = Math.round((height - icon) / 2);
  const textX = start + icon + Math.round(height * 0.12);
  return svgDoc(width, height, `
    <rect width="${width}" height="${height}" fill="${background}"/>
    <g transform="translate(${start} ${top}) scale(${icon / 64})">${symbol}</g>
    <text x="${textX}" y="${height * 0.64}" fill="${text}" font-family="NoesisFraunces, Georgia, serif" font-size="${Math.round(height * 0.38)}" font-weight="560" letter-spacing="-${Math.round(height * 0.012)}">Noesis</text>
  `, "Logo Noesis sobre fondo");
}

async function writeSvg(relative, svg) {
  const target = path.join(root, relative);
  ensure(path.dirname(target));
  fs.writeFileSync(target, svg, "utf8");
  return target;
}

async function render(relative, svg, width, height, purpose, background = null) {
  const target = path.join(root, relative);
  ensure(path.dirname(target));
  let pipeline = sharp(Buffer.from(svg));
  if (width || height) pipeline = pipeline.resize(width || null, height || null, { fit: "fill" });
  if (background) pipeline = pipeline.flatten({ background });
  await pipeline.png({ compressionLevel: 9 }).toFile(target);
  const meta = await sharp(target).metadata();
  const bytes = fs.readFileSync(target);
  assets.push({
    path: relative.replaceAll("\\", "/"),
    width: meta.width,
    height: meta.height,
    alpha: Boolean(meta.hasAlpha),
    purpose,
    sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
  });
}

function markDoc(variant = "primary") {
  const variants = {
    primary: mark(),
    forest: mark({ outer: C.forest, inner: C.forest, center: C.forest, dot: C.cream }),
    white: mark({ outer: C.cream, inner: C.cream, center: C.cream, dot: C.forest }),
  };
  return svgDoc(64, 64, variants[variant], `Símbolo Noesis ${variant}`);
}

function socialProfile(size = 1080) {
  const tile = Math.round(size * 0.48);
  const start = Math.round((size - tile) / 2);
  const icon = Math.round(tile * 0.62);
  const iconStart = Math.round((size - icon) / 2);
  return svgDoc(size, size, `
    <rect width="${size}" height="${size}" fill="${C.forest}"/>
    <circle cx="${size / 2}" cy="${size / 2}" r="${size * 0.43}" fill="none" stroke="${C.lightTeal}" stroke-opacity=".18" stroke-width="2"/>
    <rect x="${start}" y="${start}" width="${tile}" height="${tile}" rx="${tile * 0.22}" fill="${C.cream}"/>
    <g transform="translate(${iconStart} ${iconStart}) scale(${icon / 64})">${mark()}</g>
  `, "Avatar social de Noesis");
}

function socialAvatar(size = 1080) {
  const icon = Math.round(size * 0.64);
  const iconStart = Math.round((size - icon) / 2);
  const outlinedMark = `<g>
    <polygon points="32,3 38,26 61,32 38,38 32,61 26,38 3,32 26,26" fill="${C.teal}" stroke="${C.ink}" stroke-width="2.1" stroke-linejoin="round"/>
    <polygon points="32,13 36,28 51,32 36,36 32,51 28,36 13,32 28,28" fill="${C.forest}"/>
    <circle cx="32" cy="32" r="6.5" fill="${C.forest}"/>
    <circle cx="32" cy="32" r="3.4" fill="${C.cream}"/>
  </g>`;
  return svgDoc(size, size, `
    <rect width="${size}" height="${size}" fill="${C.forest}"/>
    <g transform="translate(${iconStart} ${iconStart}) scale(${icon / 64})">${outlinedMark}</g>
  `, "Avatar social de Noesis: estrella original sobre verde bosque y contorno exterior oscuro");
}

function coverSvg(width, height, platform) {
  const compact = height < 800;
  const markSize = Math.round(height * (compact ? 0.32 : 0.22));
  const left = Math.round(width * 0.12);
  const top = Math.round((height - markSize) / 2);
  const textX = left + markSize + Math.round(height * 0.16);
  const titleSize = Math.round(height * (compact ? 0.22 : 0.105));
  const subSize = Math.round(titleSize * 0.32);
  return svgDoc(width, height, `
    <rect width="${width}" height="${height}" fill="${C.deep}"/>
    <circle cx="${width * 0.86}" cy="${height * 0.18}" r="${height * 0.72}" fill="${C.teal}" opacity=".11"/>
    <circle cx="${width * 0.86}" cy="${height * 0.18}" r="${height * 0.46}" fill="none" stroke="${C.lightTeal}" stroke-opacity=".2" stroke-width="2"/>
    <rect x="${left}" y="${top}" width="${markSize}" height="${markSize}" rx="${markSize * 0.22}" fill="${C.cream}"/>
    <g transform="translate(${left + markSize * 0.19} ${top + markSize * 0.19}) scale(${markSize * 0.62 / 64})">${mark()}</g>
    <text x="${textX}" y="${height * 0.47}" fill="${C.cream}" font-family="NoesisFraunces, Georgia, serif" font-size="${titleSize}" font-weight="540" letter-spacing="-${Math.max(1, titleSize * 0.025)}">Haz tu trabajo.</text>
    <text x="${textX}" y="${height * 0.47 + titleSize * 1.02}" fill="${C.cream}" font-family="NoesisFraunces, Georgia, serif" font-size="${titleSize}" font-weight="540" letter-spacing="-${Math.max(1, titleSize * 0.025)}">Noesis ordena el negocio.</text>
    <text x="${textX}" y="${height * 0.82}" fill="${C.lightTeal}" font-family="Arial, sans-serif" font-size="${subSize}" font-weight="600" letter-spacing="${subSize * 0.05}">MÁS TIEMPO · MENOS PAPELEO · TODO BAJO CONTROL</text>
  `, `Portada ${platform} de Noesis`);
}

function templateSvg(width, height, tone = "cream") {
  const dark = tone === "forest";
  const bg = dark ? C.forest : C.cream;
  const ink = dark ? C.cream : C.forest;
  const line = dark ? C.lightTeal : C.teal;
  const pad = Math.round(width * 0.075);
  const badge = Math.round(width * 0.075);
  return svgDoc(width, height, `
    <rect width="${width}" height="${height}" fill="${bg}"/>
    <circle cx="${width * 0.9}" cy="${height * 0.12}" r="${width * 0.22}" fill="${line}" opacity=".08"/>
    <rect x="${pad}" y="${pad}" width="${badge}" height="${badge}" rx="${badge * 0.22}" fill="${dark ? C.cream : C.forest}"/>
    <g transform="translate(${pad + badge * 0.18} ${pad + badge * 0.18}) scale(${badge * 0.64 / 64})">${dark ? mark() : mark({ outer: C.lightTeal, inner: C.cream, center: C.cream, dot: C.forest })}</g>
    <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="${line}" stroke-opacity=".35"/>
    <text x="${pad}" y="${height - pad * 0.42}" fill="${ink}" font-family="Arial, sans-serif" font-size="${Math.round(width * 0.025)}" font-weight="700" letter-spacing="${Math.round(width * 0.002)}">NOESIS · BYNOESIS.COM</text>
  `, "Plantilla de contenido Noesis");
}

function paletteBoard() {
  const swatches = [
    ["VERDE BOSQUE", C.forest, "#14463B", C.cream],
    ["TEAL", C.teal, "#2E8B74", "#FFFFFF"],
    ["CREMA", C.cream, "#F4F1E8", C.ink],
    ["TINTA", C.ink, "#15211C", C.cream],
    ["SALVIA", C.sage, "#E4EFE9", C.ink],
    ["BLANCO CÁLIDO", C.warm, "#FAF8F3", C.ink],
  ];
  const cards = swatches.map(([name, color, hex, text], i) => {
    const x = 80 + (i % 3) * 500;
    const y = 260 + Math.floor(i / 3) * 300;
    return `<rect x="${x}" y="${y}" width="430" height="220" rx="24" fill="${color}"/>
      <text x="${x + 30}" y="${y + 150}" fill="${text}" font-family="Arial, sans-serif" font-size="25" font-weight="700">${name}</text>
      <text x="${x + 30}" y="${y + 187}" fill="${text}" opacity=".78" font-family="Arial, sans-serif" font-size="22">${hex}</text>`;
  }).join("");
  return svgDoc(1600, 1000, `
    <rect width="1600" height="1000" fill="${C.warm}"/>
    <text x="80" y="105" fill="${C.forest}" font-family="NoesisFraunces, Georgia, serif" font-size="64" font-weight="560">Paleta Noesis</text>
    <text x="80" y="160" fill="${C.muted}" font-family="Arial, sans-serif" font-size="25">Calma, control y oficio. Verde con moderación; crema como lienzo.</text>
    ${cards}
    <text x="80" y="930" fill="${C.forest}" font-family="NoesisFraunces, Georgia, serif" font-size="38">Fraunces habla · Inter organiza</text>
  `, "Paleta de marca Noesis");
}

function brandBoard() {
  return svgDoc(1800, 1200, `
    <rect width="1800" height="1200" fill="${C.cream}"/>
    <rect width="1800" height="245" fill="${C.deep}"/>
    <g transform="translate(85 55) scale(2.1)">${mark({ outer: C.lightTeal, inner: C.cream, center: C.cream, dot: C.deep })}</g>
    <text x="265" y="158" fill="${C.cream}" font-family="NoesisFraunces, Georgia, serif" font-size="98" font-weight="560" letter-spacing="-3">Noesis</text>
    <text x="1120" y="143" fill="${C.lightTeal}" font-family="Arial, sans-serif" font-size="26" font-weight="700" letter-spacing="3">SISTEMA DE MARCA · 2026</text>

    <text x="85" y="340" fill="${C.forest}" font-family="NoesisFraunces, Georgia, serif" font-size="48">Haz tu trabajo. Noesis te ordena el negocio.</text>
    <text x="85" y="390" fill="${C.muted}" font-family="Arial, sans-serif" font-size="24">Tiempo, claridad y control para el autónomo de servicios.</text>

    <rect x="85" y="465" width="520" height="250" rx="24" fill="#FFFFFF"/>
    <g transform="translate(125 505) scale(2.45)">${mark()}</g>
    <text x="330" y="630" fill="${C.forest}" font-family="NoesisFraunces, Georgia, serif" font-size="78" font-weight="560" letter-spacing="-2">Noesis</text>

    <rect x="640" y="465" width="520" height="250" rx="24" fill="${C.forest}"/>
    <g transform="translate(680 505) scale(2.45)">${mark({ outer: C.lightTeal, inner: C.cream, center: C.cream, dot: C.forest })}</g>
    <text x="885" y="630" fill="${C.cream}" font-family="NoesisFraunces, Georgia, serif" font-size="78" font-weight="560" letter-spacing="-2">Noesis</text>

    <rect x="1195" y="465" width="520" height="250" rx="24" fill="${C.sage}"/>
    <rect x="1360" y="505" width="190" height="190" rx="44" fill="${C.forest}"/>
    <g transform="translate(1397 542) scale(1.82)">${mark({ outer: C.lightTeal, inner: C.cream, center: C.cream, dot: C.forest })}</g>

    ${[[C.forest,"#14463B"],[C.teal,"#2E8B74"],[C.cream,"#F4F1E8"],[C.ink,"#15211C"],[C.sage,"#E4EFE9"]].map(([color, label], i) => `<rect x="${85 + i * 325}" y="800" width="280" height="150" rx="20" fill="${color}"/><text x="${105 + i * 325}" y="990" fill="${C.ink}" font-family="Arial, sans-serif" font-size="22">${label}</text>`).join("")}
    <text x="85" y="1095" fill="${C.forest}" font-family="NoesisFraunces, Georgia, serif" font-size="46">Noesis lleva la oficina.</text>
    <text x="85" y="1140" fill="${C.muted}" font-family="Arial, sans-serif" font-size="23">Tú haces tu trabajo y mantienes el control.</text>
  `, "Sistema de marca Noesis");
}

async function main() {
  for (const dir of ["logos/png/mark", "logos/png/lockup", "logos/png/wordmark", "logos/png/background", "social", "templates/editable", "templates/png", "palette", "previews", "sources"]) ensure(path.join(root, dir));

  const primaryLogo = logoSvg();
  const reverseLogo = logoSvg({ reverse: true });
  const monoLogo = logoSvg({ monochrome: true });
  const wordmark = logoSvg({ wordmarkOnly: true });
  const wordmarkReverse = logoSvg({ reverse: true, wordmarkOnly: true });
  await writeSvg("sources/noesis-logo-horizontal-primary.svg", primaryLogo);
  await writeSvg("sources/noesis-logo-horizontal-reverse.svg", reverseLogo);
  await writeSvg("sources/noesis-logo-horizontal-monochrome.svg", monoLogo);
  await writeSvg("sources/noesis-wordmark-primary.svg", wordmark);
  await writeSvg("sources/noesis-wordmark-reverse.svg", wordmarkReverse);
  await writeSvg("sources/noesis-mark-monochrome-forest.svg", markDoc("forest"));
  await writeSvg("sources/noesis-mark-monochrome-white.svg", markDoc("white"));

  for (const size of [32, 64, 128, 256, 512, 1024]) {
    await render(`logos/png/mark/noesis-mark-primary-${size}.png`, markDoc("primary"), size, size, "Símbolo primario transparente");
  }
  for (const size of [128, 256, 512, 1024]) {
    await render(`logos/png/mark/noesis-mark-forest-${size}.png`, markDoc("forest"), size, size, "Símbolo monocromo bosque transparente");
    await render(`logos/png/mark/noesis-mark-white-${size}.png`, markDoc("white"), size, size, "Símbolo inverso transparente");
  }
  for (const width of [512, 1024, 2048]) {
    const height = Math.round(width * 180 / 640);
    await render(`logos/png/lockup/noesis-logo-primary-${width}.png`, primaryLogo, width, height, "Logo horizontal primario transparente");
    await render(`logos/png/lockup/noesis-logo-reverse-${width}.png`, reverseLogo, width, height, "Logo horizontal inverso transparente");
    await render(`logos/png/lockup/noesis-logo-monochrome-${width}.png`, monoLogo, width, height, "Logo horizontal monocromo transparente");
  }
  for (const width of [512, 1024]) {
    const height = Math.round(width * 180 / 640);
    await render(`logos/png/wordmark/noesis-wordmark-primary-${width}.png`, wordmark, width, height, "Wordmark primario transparente");
    await render(`logos/png/wordmark/noesis-wordmark-reverse-${width}.png`, wordmarkReverse, width, height, "Wordmark inverso transparente");
  }
  await render("logos/png/background/noesis-logo-on-cream-1600x600.png", logoPlate(1600, 600, C.cream), 1600, 600, "Logo centrado sobre crema");
  await render("logos/png/background/noesis-logo-on-white-1600x600.png", logoPlate(1600, 600, "#FFFFFF"), 1600, 600, "Logo centrado sobre blanco");
  await render("logos/png/background/noesis-logo-on-forest-1600x600.png", logoPlate(1600, 600, C.forest, true), 1600, 600, "Logo inverso centrado sobre verde bosque");

  const profile = socialAvatar();
  await render("social/instagram-profile-1080.png", profile, 1080, 1080, "Avatar Instagram preparado para recorte circular");
  await render("social/facebook-profile-1080.png", profile, 1080, 1080, "Avatar Facebook preparado para recorte circular");
  await render("social/linkedin-logo-400.png", profile, 400, 400, "Logo de página LinkedIn");
  await render("social/youtube-profile-800.png", profile, 800, 800, "Avatar YouTube");
  await render("social/linkedin-cover-4200x700.png", coverSvg(4200, 700, "LinkedIn"), 4200, 700, "Portada de página LinkedIn");
  await render("social/facebook-cover-1640x856.png", coverSvg(1640, 856, "Facebook"), 1640, 856, "Portada Facebook 2x");
  await render("social/open-graph-1200x630.png", coverSvg(1200, 630, "Open Graph"), 1200, 630, "Imagen para enlaces compartidos");

  const templateSpecs = [
    ["square", 1080, 1080],
    ["portrait", 1080, 1350],
    ["story", 1080, 1920],
  ];
  for (const [name, width, height] of templateSpecs) {
    for (const tone of ["cream", "forest"]) {
      const svg = templateSvg(width, height, tone);
      await writeSvg(`templates/editable/noesis-${name}-${tone}.svg`, svg);
      await render(`templates/png/noesis-${name}-${tone}.png`, svg, width, height, `Fondo ${name} ${tone} para contenido`);
    }
  }

  await render("palette/noesis-palette-board.png", paletteBoard(), 1600, 1000, "Lámina visual de paleta y tipografía");
  await render("previews/noesis-brand-board.png", brandBoard(), 1800, 1200, "Vista general para control de marca");

  const appIcons = [["apple-touch-icon",180],["app-icon",192],["app-icon",512],["maskable-icon",512]];
  for (const [name, size] of appIcons) {
    await render(`logos/png/mark/${name}-${size}.png`, socialProfile(size), size, size, `Icono ${name}`);
  }

  assets.sort((a, b) => a.path.localeCompare(b.path));
  fs.writeFileSync(path.join(root, "manifest.json"), JSON.stringify({
    brand: "Noesis",
    version: "1.2.2",
    generated_at: "2026-08-31",
    source_mark: "sources/noesis-mark-master.svg",
    assets,
  }, null, 2) + "\n", "utf8");
  console.log(`Branding generado: ${assets.length} PNG y ${assets.reduce((sum, asset) => sum + fs.statSync(path.join(root, asset.path)).size, 0)} bytes.`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
