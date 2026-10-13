"""Lo que comparten las pruebas del CRM: una base temporal y una hoja de ejemplo."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from noesis import config, db

ENLACE = ("https://docs.google.com/spreadsheets/d/"
          "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcd/edit?gid=5#gid=5")

HOJA = (
    "EMPRESA,DIRECCION,ESTADO,TELEFONO,EMAIL IA,PAGINA WEB,PROVINCIA,"
    "VERIFICACION CORREO\n"
    'Gestoria Pons,"Carrer Major 2, 25001 Lleida",WEB ACTIVA,973 22 33 44,'
    "info@gestoriapons.cat,https://gestoriapons.cat,LLEIDA,Buzón existe\n"
    'Assessoria Riera,"Av. Jaume I 10, 17001 Girona",WEB ACTIVA,,'
    "hola@riera.cat,,,\n"
    "Asesoría Ebro,,WEB ACTIVA,976 11 22 33,info@ebro.es,,Zaragoza,\n"
)


class ConBase(unittest.TestCase):
    """Cada prueba, su base vacía y migrada."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "test.db",
            BACKUP_DIR=Path(self.temp.name) / "backups",
            DOCS_PATH=Path(self.temp.name) / "docs")
        self.settings.start()
        db.init_db()

    def tearDown(self):
        self.settings.stop()
        self.temp.cleanup()
