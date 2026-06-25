# Decisiones

Registro de decisiones importantes y su porqué (las más recientes arriba).

## Posicionamiento: suite completa, construida modular
El founder eligió "suite completa desde el inicio" frente a empezar solo por el
copiloto proactivo. Se construye modular para que no se vuelva inmanejable.
Diferenciador real: orquestación + agenda, donde [[Competencia|Forjia]] es débil.

## No copiar código de competidores
El código de Holded/Forjia es propietario: copiarlo sería ilegal y una trampa. Se
copian **ideas/UX** y se usa open-source. Ver [[Competencia]].

## Arquitectura híbrida de IA (coste/privacidad)
Cerebro local por reglas para lo rutinario (gratis, interno) + IA en la nube solo
para lo complejo. Motivo: por debajo de ~500M tokens/mes no compensa auto-hospedar.
Ver [[Investigación]] y [[Arquitectura]].

## Mínimas dependencias externas
Hash de contraseñas con stdlib (PBKDF2), Chart.js servido en local, sin Tailwind.
Motivo: coste, privacidad y control. Ver [[Arquitectura]].

## No reconstruir Verifactu
Se integrará vía API de un proveedor homologado (Holded/Quipu) en vez de
construir la parte regulada. Ver [[Fiscalidad]].

## Marca
Paleta del logo: verde bosque #14463b + teal #2e8b74 + crema #f4f1e8. Dominio
previsto: bynoesis.com. Ver [[Producto]].
