import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qt.core import QApplication
from calibre.gui2.store.search_result import SearchResult

import libgen_plugin as plugin


class FakeResponse:
    def __init__(self, data):
        self.data = io.BytesIO(data)

    def read(self):
        return self.data.read()

    def close(self):
        self.data.close()


class FakeBrowser:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def open(self, url, data=None, timeout=None):
        self.calls.append((url, data, timeout))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        if isinstance(response, dict):
            response = json.dumps(response).encode()
        return FakeResponse(response)


def api_result(result):
    return {"isError": False, "result": result}


def book(book_id="123", **fields):
    return {
        "id": book_id, "title": "The Republic", "author": ["Plato"],
        "fileExtension": "epub", "fileSize": 1048576,
        "year": 1901, "language": "eng", **fields,
    }


def search_result():
    result = SearchResult()
    result.detail_item = "https://libgen.net/book/123"
    result.formats = "EPUB"
    return result


class LayoutTests(unittest.TestCase):
    def test_legacy_search_preserves_metadata_and_selected_mirror(self):
        html = b'''<table class="table table-striped"><thead><tr>
        <th>Cover</th><th>Title</th><th>Author(s)</th><th>Year</th><th>Pages</th>
        <th>Size</th><th>Ext</th><th>Mirrors</th></tr></thead><tbody><tr>
        <td><img src="/cover.jpg"></td><td>The Republic</td><td>Plato</td>
        <td>1901</td><td>300</td><td>1 MB</td><td>epub</td>
        <td><a href="https://libgen.bz/get.php?md5=abc">Download</a></td>
        </tr></tbody></table>'''
        br = FakeBrowser([html])
        with patch.object(plugin, "browser", return_value=br):
            results = plugin.search_libgen("Plato", base_url="https://libgen.gl")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "The Republic")
        self.assertEqual(results[0].author, "Plato")
        self.assertEqual(results[0].formats, "EPUB")
        self.assertEqual(results[0].detail_item, "https://libgen.gl/ads.php?md5=abc")
        self.assertEqual(results[0].cover_url, "https://libgen.gl/cover.jpg")

    def test_search_dispatch_and_pagination_keep_book_identity(self):
        br = FakeBrowser([
            api_result({"books": [book()], "total": 3}),
            api_result({"books": [book(), book("456", title="Other Book")], "total": 3}),
        ])
        with patch.object(plugin, "browser", return_value=br):
            results = plugin.search_libgen("Plato & Republic", max_results=2, base_url="https://libgen.net")
        self.assertEqual([result.detail_item for result in results], [
            "https://libgen.net/book/123", "https://libgen.net/book/456",
        ])
        self.assertEqual(results[0].author, "Plato")
        self.assertEqual(results[0].formats, "EPUB")
        self.assertEqual(results[0].price, "1901\neng")
        first_query = urllib.parse.parse_qs(urllib.parse.urlsplit(br.calls[0][0]).query)
        self.assertEqual(first_query["query"], ["Plato & Republic"])
        self.assertEqual(first_query["collection"], ["libgen"])
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(br.calls[1][0]).query)["from"], ["1"])
        self.assertGreater(br.calls[0][2], br.calls[1][2])

    def test_empty_results_stop_without_extra_requests(self):
        br = FakeBrowser([api_result({"books": [], "total": 0})])
        with patch.object(plugin, "browser", return_value=br):
            self.assertEqual(plugin.search_spa("unknown", 10, 60, "https://libgen.net"), [])
        self.assertEqual(len(br.calls), 1)

    def test_api_error_is_distinct_from_no_matches(self):
        br = FakeBrowser([{"isError": True, "result": "service unavailable"}])
        with patch.object(plugin, "browser", return_value=br):
            with self.assertRaisesRegex(ValueError, "could not complete"):
                plugin.search_spa("Plato", 10, 60, "https://libgen.net")

    def test_repeated_page_stops(self):
        br = FakeBrowser([
            api_result({"books": [book()], "total": 100}),
            api_result({"books": [book()], "total": 100}),
        ])
        with patch.object(plugin, "browser", return_value=br):
            self.assertEqual(len(plugin.search_spa("Plato", 10, 60, "https://libgen.net")), 1)

    def test_resolver_posts_token_and_preserves_explicit_file_url(self):
        br = FakeBrowser([
            api_result({"links": ["https://files.example/?l=a%2Bb%2Fc%3D"]}),
            {"id": "123", "downloadLink": "./api/download?id=123", "imageLink": "/cover.jpg"},
        ])
        result = search_result()
        with patch.object(plugin, "browser", return_value=br):
            self.assertTrue(plugin.LibgenStorePlugin.get_details(result, timeout=5))
        self.assertEqual(result.downloads, {"EPUB": "https://files.example/api/download?id=123"})
        self.assertEqual(result.cover_url, "https://files.example/cover.jpg")
        self.assertEqual(br.calls[1][1], b"")
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlsplit(br.calls[1][0]).query)["l"], ["a+b/c="])
        self.assertLessEqual(br.calls[0][2], 5)

    def test_wrong_book_and_landing_pages_never_become_downloads(self):
        br = FakeBrowser([
            api_result({"links": ["https://files.example/?l=one", "https://files.example/?l=two"]}),
            {"id": "999", "downloadLink": "./api/download?id=999"},
            {"id": "123", "downloadLink": "./landing?id=123"},
        ])
        result = search_result()
        with patch.object(plugin, "browser", return_value=br):
            self.assertFalse(plugin.resolve_spa_download(result, 60))
        self.assertEqual(result.downloads, {})
        self.assertEqual(result.detail_item, "https://libgen.net/book/123")

    def test_landing_failure_tries_next_provider(self):
        br = FakeBrowser([
            api_result({"links": ["https://first.example/?l=one", "https://second.example/?l=two"]}),
            OSError("unavailable"),
            {"id": "123", "downloadLink": "./api/download?id=123"},
        ])
        result = search_result()
        with patch.object(plugin, "browser", return_value=br):
            self.assertTrue(plugin.resolve_spa_download(result, 60))
        self.assertEqual(result.downloads["EPUB"], "https://second.example/api/download?id=123")

    def test_invalid_cover_does_not_discard_valid_download(self):
        br = FakeBrowser([
            api_result({"links": ["https://files.example/?l=one"]}),
            {"id": "123", "downloadLink": "./api/download?id=123", "imageLink": 7},
        ])
        result = search_result()
        with patch.object(plugin, "browser", return_value=br):
            self.assertTrue(plugin.resolve_spa_download(result, 60))
        self.assertEqual(result.downloads["EPUB"], "https://files.example/api/download?id=123")

    def test_error_page_is_not_a_legacy_download(self):
        result = search_result()
        result.detail_item = "https://libgen.bz/ads.php?md5=abc"
        br = FakeBrowser([b'<table><tr><td>Database limit exceeded <a href="/report">Report</a></td></tr></table>'])
        with patch.object(plugin, "browser", return_value=br):
            self.assertFalse(plugin.LibgenStorePlugin.get_details(result))
        self.assertEqual(result.downloads, {})

    def test_legacy_failure_returns_false_after_bounded_retries(self):
        result = search_result()
        result.detail_item = "https://libgen.bz/ads.php?md5=abc"
        br = FakeBrowser([OSError("500"), OSError("500"), OSError("500")])
        with patch.object(plugin, "browser", return_value=br), patch.object(plugin.time, "sleep"):
            self.assertFalse(plugin.LibgenStorePlugin.get_details(result, 7))
        self.assertEqual(len(br.calls), 3)
        self.assertTrue(all(0 < timeout <= 7 for _, _, timeout in br.calls))
        self.assertEqual(result.downloads, {})

    def test_legacy_download_ignores_unrelated_links(self):
        result = search_result()
        result.detail_item = "https://libgen.bz/ads.php?md5=abc"
        br = FakeBrowser([b'<table><tr><td><a href="/report">Report</a><a href="/get.php?md5=abc">GET</a></td></tr></table>'])
        with patch.object(plugin, "browser", return_value=br):
            self.assertTrue(plugin.LibgenStorePlugin.get_details(result))
        self.assertEqual(result.downloads["EPUB"], "https://libgen.bz/get.php?md5=abc")

    def test_settings_choice_applies_to_new_searches_and_persists(self):
        config = {"mirror": "https://libgen.bz"}
        store = plugin.LibgenStorePlugin(None, "Library Genesis", config=config)
        widget = store.config_widget()
        widget.mirror.setCurrentIndex(widget.mirror.findData("https://libgen.net"))
        store.save_settings(widget)
        self.assertEqual(config["mirror"], "https://libgen.net")
        self.assertEqual(store.libgen_url, "https://libgen.net")
        self.assertEqual(plugin.LibgenStorePlugin(None, "Library Genesis", config=config).libgen_url, "https://libgen.net")


if __name__ == "__main__":
    app = QApplication.instance() or QApplication([])
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LayoutTests)
    result = unittest.TextTestRunner().run(suite)
    raise SystemExit(not result.wasSuccessful())
