import io
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src import enrichment_service

app = enrichment_service.app


class UploadFileTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.incoming_dir = self.tmpdir.name
        self.incoming_patch = patch.object(
            enrichment_service, "INCOMING_DOCS_DIR", self.incoming_dir
        )
        self.incoming_patch.start()

    def tearDown(self):
        self.incoming_patch.stop()
        self.tmpdir.cleanup()

    # ------------------------------------------------------------------
    # GET / — UI is served
    # ------------------------------------------------------------------

    def test_index_returns_html(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Document Analyzer", response.data)

    # ------------------------------------------------------------------
    # POST /upload-file — validation errors
    # ------------------------------------------------------------------

    def test_upload_no_file_part(self):
        response = self.client.post("/upload-file", data={})
        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertIn("error", body)

    def test_upload_empty_filename(self):
        data = {"file": (io.BytesIO(b"data"), "")}
        response = self.client.post(
            "/upload-file",
            data=data,
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_upload_unsupported_extension(self):
        data = {"file": (io.BytesIO(b"data"), "file.exe")}
        response = self.client.post(
            "/upload-file",
            data=data,
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 415)
        body = response.get_json()
        self.assertIn("error", body)
        self.assertIn(".exe", body["error"])

    # ------------------------------------------------------------------
    # POST /upload-file — webhook success (JSON response)
    # ------------------------------------------------------------------

    def test_upload_success_json_response(self):
        webhook_payload = {"analysis": "ok", "score": 0.9}
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = webhook_payload
        mock_resp.raise_for_status.return_value = None

        with patch("src.enrichment_service.http_client.post", return_value=mock_resp):
            data = {"file": (io.BytesIO(b"%PDF content"), "document.pdf")}
            response = self.client.post(
                "/upload-file",
                data=data,
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["filename"], "document.pdf")
        self.assertEqual(body["result"], webhook_payload)
        saved_file = os.path.join(self.incoming_dir, "document.pdf")
        self.assertTrue(os.path.exists(saved_file))

    def test_upload_calls_webhook_with_filename_only(self):
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = {"ok": True}
        mock_resp.raise_for_status.return_value = None

        with patch("src.enrichment_service.http_client.post", return_value=mock_resp) as mock_post:
            data = {"file": (io.BytesIO(b"%PDF content"), "document.pdf")}
            response = self.client.post(
                "/upload-file",
                data=data,
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs.get("json"), {"filename": "document.pdf"})
        self.assertNotIn("files", kwargs)

    # ------------------------------------------------------------------
    # POST /upload-file — webhook success (HTML response)
    # ------------------------------------------------------------------

    def test_upload_success_html_response(self):
        html_content = "<html><body><h1>Analysis</h1></body></html>"
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = html_content
        mock_resp.raise_for_status.return_value = None

        with patch("src.enrichment_service.http_client.post", return_value=mock_resp):
            data = {"file": (io.BytesIO(b"content"), "report.pdf")}
            response = self.client.post(
                "/upload-file",
                data=data,
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["result"], html_content)

    # ------------------------------------------------------------------
    # POST /upload-file — webhook errors
    # ------------------------------------------------------------------

    def test_upload_webhook_timeout(self):
        import requests as real_requests

        with patch(
            "src.enrichment_service.http_client.post",
            side_effect=real_requests.exceptions.Timeout,
        ):
            data = {"file": (io.BytesIO(b"content"), "doc.pdf")}
            response = self.client.post(
                "/upload-file",
                data=data,
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 504)
        self.assertIn("timed out", response.get_json()["error"])

    def test_upload_webhook_connection_error(self):
        import requests as real_requests

        with patch(
            "src.enrichment_service.http_client.post",
            side_effect=real_requests.exceptions.ConnectionError("refused"),
        ):
            data = {"file": (io.BytesIO(b"content"), "doc.pdf")}
            response = self.client.post(
                "/upload-file",
                data=data,
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 502)
        self.assertIn("error", response.get_json())

    def test_upload_webhook_http_error(self):
        import requests as real_requests

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = real_requests.exceptions.HTTPError(
            "500 Server Error"
        )

        with patch("src.enrichment_service.http_client.post", return_value=mock_resp):
            data = {"file": (io.BytesIO(b"content"), "doc.txt")}
            response = self.client.post(
                "/upload-file",
                data=data,
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 502)
        self.assertIn("error", response.get_json())


if __name__ == "__main__":
    unittest.main()
