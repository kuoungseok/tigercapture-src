class _MemoryKeyring:
    def __init__(self):
        self.data = {}

    def set_password(self, service, name, value):
        self.data[(service, name)] = value

    def get_password(self, service, name):
        return self.data.get((service, name))

    def delete_password(self, service, name):
        self.data.pop((service, name), None)


def test_stream_key_store_load_delete_with_backend():
    from app.broadcast_secrets import delete_stream_key, load_stream_key, store_stream_key

    backend = _MemoryKeyring()

    stored = store_stream_key("youtube_live", "SECRET", account="main", backend=backend)
    loaded = load_stream_key("youtube_live", account="main", backend=backend)
    deleted = delete_stream_key("youtube_live", account="main", backend=backend)
    missing = load_stream_key("youtube_live", account="main", backend=backend)

    assert stored["stored"] is True
    assert loaded["stream_key"] == "SECRET"
    assert deleted["deleted"] is True
    assert missing["found"] is False


def test_stream_key_status_reports_session_only_when_backend_missing():
    from app.broadcast_secrets import stream_key_store_status

    status = stream_key_store_status(backend=None)

    assert "storage" in status
