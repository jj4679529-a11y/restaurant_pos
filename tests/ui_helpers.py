from time import monotonic

from PySide6.QtTest import QTest


def wait_for_catalog(window, qt_app):
    """Wait for the background catalog result, not just one Qt event turn."""
    qt_app.processEvents()
    deadline = monotonic() + 5
    while window.catalog_loading and monotonic() < deadline:
        QTest.qWait(10)
    assert not window.catalog_loading, 'Catalog worker did not complete'
    assert window.catalog_retry.isHidden(), window.catalog_message.text()
