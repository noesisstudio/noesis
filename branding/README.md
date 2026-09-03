# Branding de Noesis

Paquete oficial y versionado de identidad visual. Empieza por
[`BRAND_GUIDE.md`](BRAND_GUIDE.md) y utiliza los archivos de `social/` directamente
en cada plataforma.

## Elección rápida

- Instagram/Facebook: `social/instagram-profile-1080.png` y
  `social/facebook-profile-1080.png`.
- LinkedIn: `social/linkedin-logo-400.png` y
  `social/linkedin-cover-4200x700.png`.
- Logo sobre fondo claro: `logos/png/lockup/noesis-logo-primary-1024.png`.
- Logo sobre fondo oscuro: `logos/png/lockup/noesis-logo-reverse-1024.png`.
- Logo ya compuesto con fondo: `logos/png/background/`.
- Símbolo transparente: `logos/png/mark/noesis-mark-primary-512.png`.
- Presentaciones o documentos: originales de `sources/`.
- Plantillas de contenido: `templates/png/` y sus SVG editables equivalentes.
- Perfiles sociales listos para publicar: `redes-sociales/` reúne los archivos de
  Instagram, Facebook y LinkedIn, los textos exactos de configuración, la guía en
  Word y la recomendación de reserva para YouTube y TikTok.

## Principio

El paquete conserva el símbolo que ya usa el producto. Profesionaliza sus variantes,
espaciado, tamaños y aplicaciones sin crear una identidad paralela.

Las especificaciones de LinkedIn se tomaron de su documentación oficial vigente en
agosto de 2026: logo recomendado de 400 × 400 y portada de 4200 × 700.
<https://www.linkedin.com/help/linkedin/answer/a570368>

## Regeneración

La carpeta es autónoma. Si no se usa el runtime de Codex:

```powershell
cd branding
npm install
npm run build
```

El manifiesto se reescribe con las dimensiones reales de cada PNG y el hash SHA-256
de todos los activos finales.
