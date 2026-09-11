import os
import tempfile

import database
from cogs.wash import WashSelectionView


def _use_temp_db(monkeypatch):
    db_path = os.path.join(tempfile.gettempdir(), "test_wash_view.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    monkeypatch.setattr(database, "DB_NAME", db_path)
    database.init_db()


def test_wash_view_blocks_duplicate_submission(monkeypatch):
    _use_temp_db(monkeypatch)
    view = WashSelectionView(guild_id=12345)

    assert view.begin_submission() is True
    assert view.begin_submission() is False
