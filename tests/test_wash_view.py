from cogs.wash import WashSelectionView


def test_wash_view_blocks_duplicate_submission():
    view = WashSelectionView()

    assert view.begin_submission() is True
    assert view.begin_submission() is False
