"""Compatibilidad documental.

La tabla ``documents`` y sus claves foráneas viven desde ahora en las migraciones
versionadas de :mod:`noesis.migrations`. Este módulo se conserva para no romper
imports históricos, pero ya no modifica el esquema durante el arranque.
"""
