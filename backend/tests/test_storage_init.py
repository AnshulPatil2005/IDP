import unittest
import os
import sys
import importlib
from unittest.mock import patch, MagicMock

# Add backend to sys.path so we can import app
sys.path.insert(0, os.path.join(os.getcwd(), "backend"))

class TestStorageInit(unittest.TestCase):
    def setUp(self):
        # Clean up any existing import of the module
        if 'app.services.storage' in sys.modules:
            del sys.modules['app.services.storage']

    @patch.dict(os.environ, {
        "MINIO_ENDPOINT": "minio:9000",
        "MINIO_SECURE": "false",
        "MINIO_ACCESS_KEY": "test",
        "MINIO_SECRET_KEY": "test"
    })
    def test_endpoint_prepends_http(self):
        """Test that http:// is prepended to endpoint if missing."""
        import app.services.storage
        importlib.reload(app.services.storage)

        client = app.services.storage._s3
        self.assertEqual(client.meta.endpoint_url, "http://minio:9000")

    @patch.dict(os.environ, {
        "MINIO_ENDPOINT": "minio:9000",
        "MINIO_SECURE": "true",
        "MINIO_ACCESS_KEY": "test",
        "MINIO_SECRET_KEY": "test"
    })
    def test_endpoint_prepends_https_secure(self):
        """Test that https:// is prepended to endpoint if missing and secure is true."""
        import app.services.storage
        importlib.reload(app.services.storage)

        client = app.services.storage._s3
        self.assertEqual(client.meta.endpoint_url, "https://minio:9000")

    @patch.dict(os.environ, {
        "MINIO_ENDPOINT": "http://minio:9000",
        "MINIO_SECURE": "false",
        "MINIO_ACCESS_KEY": "test",
        "MINIO_SECRET_KEY": "test"
    })
    def test_endpoint_no_double_prepend(self):
        """Test that scheme is not prepended if already present."""
        import app.services.storage
        importlib.reload(app.services.storage)

        client = app.services.storage._s3
        self.assertEqual(client.meta.endpoint_url, "http://minio:9000")

if __name__ == '__main__':
    unittest.main()
