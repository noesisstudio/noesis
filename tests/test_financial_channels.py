from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from noesis import config, db
from tests.financial_channels_contract import ChannelsContract


class FinancialChannelsSQLite(ChannelsContract, unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        settings = patch.multiple(
            config, DATABASE_URL="", DB_PATH=Path(self.temp.name) / "channel.db"
        )
        settings.start()
        self.addCleanup(settings.stop)
        db.init_db()
        self.setup_channels()
