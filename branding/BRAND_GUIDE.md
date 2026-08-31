# Noesis — guía esencial de marca

Versión 1.0 · 31 de agosto de 2026

## 1. Idea de marca

Noesis es la mano derecha del autónomo de servicios. La marca transmite calma,
control y capacidad: **haz tu trabajo; Noesis te ordena el negocio**.

La tecnología no ocupa el centro del discurso. El resultado sí: del trabajo
terminado al dinero cobrado, sin convertir al profesional en administrativo.

## 2. Nombre

- Nombre público: **Noesis**.
- Dominio y usuario digital preferente: **bynoesis.com** y **@bynoesis**.
- «ByNoesis» no sustituye al nombre principal; se reserva para URL, usuario o firma
  técnica cuando «Noesis» no esté disponible.
- No usar «Nosis», «Novesis», «Noésis» ni escribir el nombre íntegro en mayúsculas.

## 3. Sistema de logo

### Símbolo

La estrella de cuatro puntas representa una lectura clara del negocio: Noesis
detecta lo que importa y devuelve dirección. Se conserva su geometría original.

### Versiones

- **Logo horizontal primario:** símbolo + Noesis en verde bosque. Uso preferente
  sobre crema, blanco o fotografía muy clara.
- **Logo horizontal inverso:** símbolo claro + Noesis en crema. Uso sobre verde
  bosque o fondos oscuros.
- **Símbolo primario:** aplicaciones, favicon, marca de agua y espacios cuadrados.
- **Símbolo monocromo:** grabados, documentos a una tinta o restricciones técnicas.
- **Avatar social:** composición del símbolo dentro de una pastilla crema sobre
  verde bosque. Está preparada para recorte circular; no sustituye al logo maestro.

### Zona de seguridad

Mantener alrededor del logo un espacio mínimo equivalente al diámetro del círculo
central del símbolo. Ningún texto, borde o fotografía debe entrar en esa zona.

### Tamaño mínimo

- Símbolo digital: 24 px.
- Logo horizontal digital: 120 px de ancho.
- Impresión: símbolo 8 mm; logo horizontal 28 mm.

### No hacer

- No deformar, rotar ni añadir sombras al símbolo.
- No recolorear con tonos ajenos a la paleta.
- No usar el logo horizontal dentro de un avatar circular.
- No situar la versión primaria sobre fondos sin contraste.
- No añadir eslóganes pegados al logo maestro.

## 4. Paleta

| Color | HEX | Papel dentro de la marca |
|---|---|---|
| Verde bosque | `#14463B` | Identidad, acciones y fondos principales |
| Teal | `#2E8B74` | Acentos y detalle del símbolo |
| Crema | `#F4F1E8` | Lienzo cálido y contraste |
| Tinta | `#15211C` | Texto principal |
| Salvia | `#E4EFE9` | Fondos suaves y destacados |
| Blanco cálido | `#FAF8F3` | Superficies secundarias |
| Verde profundo | `#102820` | Fondos editoriales oscuros |

Ámbar y rojo son colores funcionales, no colores promocionales. Se reservan para
avisos y errores.

## 5. Tipografía

- **Fraunces:** titulares, frases de marca, recomendaciones y wordmark. Peso
  habitual 500–600. Da la sensación de que alguien competente está hablando.
- **Inter:** cuerpo, subtítulos, cifras, pies, formularios y contenido práctico.
  Peso habitual 400–700.

No usar Fraunces para tablas ni bloques largos. No usar Inter pesado para imitar el
wordmark.

## 6. Fotografía y vídeo

- Personas reales trabajando; manos, herramientas, furgonetas, obras y momentos de
  organización al terminar la jornada.
- Luz natural, tonos cálidos y escenas creíbles. Evitar oficinas de stock, robots,
  cerebros luminosos y estéticas de «IA futurista».
- En vídeo, el oficio y el problema aparecen antes que la interfaz.
- Cuando aparezca producto, mostrar una sola acción comprensible por pieza.

## 7. Voz

Noesis habla de tú, con frases cortas y una conclusión primero. Es cercana, directa
y tranquila. Puede usar humor cotidiano, pero no banaliza dinero, fiscalidad,
seguridad ni errores.

Correcto: «Has terminado el trabajo. ¿Ya lo has facturado?»

Incorrecto: «Revoluciona tu gestión empresarial mediante agentes de IA».

## 8. Uso en redes

- El avatar oficial es `social/*-profile-*`, no el SVG transparente sin fondo.
- Las portadas mantienen texto y logo en la zona central segura.
- Las plantillas son fondos de trabajo: añadir una sola idea por pieza, respetar
  márgenes y no reducir el logo.
- Instagram/Facebook: priorizar identificación y demostración.
- LinkedIn: credibilidad, fundadores, aprendizaje y alianzas.

## 9. Estructura del paquete

- `sources/`: originales vectoriales y lockups maestros.
- `logos/png/`: exportaciones transparentes por uso y tamaño.
- `logos/png/background/`: composiciones sobre crema, blanco y verde listas para
  entregar sin riesgo de contraste.
- `social/`: avatares y portadas listas para subir.
- `templates/`: fondos editables SVG y exportaciones PNG.
- `palette/`: colores en JSON, CSS y lámina visual.
- `previews/`: hojas de control para revisar el sistema de un vistazo.
- `manifest.json`: inventario técnico con dimensiones y finalidad.

Regenerar las exportaciones con:

```powershell
cd branding
npm install
npm run build
```

El script usa `sharp` como dependencia de desarrollo aislada. Los originales y
exportaciones finales permanecen versionados para que el equipo no dependa del
generador para utilizarlos.
