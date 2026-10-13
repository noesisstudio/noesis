# Fingerprints golden del diseño — públicos, no autoridad

[Contrato](SCHEMA-LINEAGE-75-80-contract.md), [catálogo](SCHEMA-LINEAGE-75-80-catalog-design.json).

Calculados sólo sobre metadata de nombres/versiones del repositorio. No datos de DB, no conexión, no ejecución de migraciones.

| Prefijo | SHA-256 |
|---|---|
| canonical0 | `fbd9ee1e2139d2da607e41699146f3856957f50a3e90e4b1b2f9f52d60c1833f` | <!-- pragma: allowlist secret; public lineage golden -->
| canonical1 | `a97aa7b0d90c757d01dada6e30bf94f039302b36415d6a9a9bf43d53866dd98c` | <!-- pragma: allowlist secret; public lineage golden -->
| canonical73 | `84bfa3c59b03c24ad79a4db13017c0dac566cba39de61cb5216ca419e715118f` | <!-- pragma: allowlist secret; public lineage golden -->
| canonical74 | `ee2de64c6e47629811c6cee2bfa8f28fea66bb9e23e28caa50bc0b62db697e24` | <!-- pragma: allowlist secret; public lineage golden -->
| canonical75 | `289b8eb580edd4c45d2de40233ffd7dfc193999b10f49825661cba18905696a1` | <!-- pragma: allowlist secret; public lineage golden -->
| canonical76 | `788e0d411d24db832be5b8a0cfe2967842eb7e53cb9fb71fa0480adacfe9d389` | <!-- pragma: allowlist secret; public lineage golden -->
| canonical77 | `ef51667e29a93a498f977c8f8c1154def3e0571f5235a24c204c4159e2da0d34` | <!-- pragma: allowlist secret; public lineage golden -->
| canonical78 | `636563f792ef06fb12d180cfc4c35cb78eb273b7576a59b4465675ebdd726c7d` | <!-- pragma: allowlist secret; public lineage golden -->
| canonical79 | `b38395462ad53463ebfc86a9d3d32d02d055893c8f346ad8581cfc34f682291d` | <!-- pragma: allowlist secret; public lineage golden -->
| canonical80 | `5d395094c4ea3df3f91d5781a204d203ee6f55c32ff41495d385b1c07efede8d` | <!-- pragma: allowlist secret; public lineage golden -->
| legacyFinancial79 | `70b85d82938a0c6ab9f98153a648fabcf4a442bb26866f389e49844189895e3a` | <!-- pragma: allowlist secret; public lineage golden -->

Clave advisory int64 con signo: `2533761095082033151`; misma namespace para upgrade/downgrade/bridge, sin número de esquema ni SHA de release.

El0 identifica la lista vacía, no demuestra que una base esté vacía. El perfil físico y las reglas de compatibilidad siguen obligatorios.
