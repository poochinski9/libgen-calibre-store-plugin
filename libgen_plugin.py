# -*- coding: utf-8 -*-
# License: GPLv3 Copyright: 2024, poochinski9
from __future__ import absolute_import, division, print_function, unicode_literals

import json
import logging
import re
import sys
import time
import urllib.parse
from contextlib import closing

from PyQt5.Qt import QComboBox, QLabel, QUrl
from bs4 import BeautifulSoup
from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig, BasicStoreConfigWidget
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog
from urllib.request import urlopen

# Live instances can be checked at https://open-slum.org
SPA_MIRRORS = [
    "https://libgen.me",
    "https://libgen.net",
    "https://libgen.xyz",
    "https://libgen.pw",
    "https://randombook.org",
]
LIBGEN_MIRRORS = [
    "https://libgen.bz",
    "https://libgen.vg",
    "https://libgen.gl",
    "https://libgen.la",
] + SPA_MIRRORS
AUTO_MIRROR = "auto"
USER_AGENT = "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko"

# Declare global variables at the module level
title_index = None
image_index = None
author_index = None
year_index = None
pages_index = None
size_index = None
ext_index = None
mirrors_index = None

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

#####################################################################
# Plug-in base class
#####################################################################
def search_libgen(query, max_results=10, timeout=60, base_url=None):
    base_url = base_url or check_url(LIBGEN_MIRRORS)
    if is_spa_url(base_url):
        return search_spa(query, max_results, timeout, base_url)
    res = "25" if max_results <= 25 else "50" if max_results <= 50 else "100"
    encoded_query = urllib.parse.quote(query)
    search_url = f"{base_url}/index.php?req={encoded_query}&columns[]=t&columns[]=a&columns[]=s&columns[]=y&columns[]=p&columns[]=i&objects[]=f&objects[]=e&objects[]=s&objects[]=a&objects[]=p&objects[]=w&topics[]=l&topics[]=c&topics[]=f&topics[]=a&topics[]=m&topics[]=r&topics[]=s&res={res}&covers=on&gmode=on&filesuns=all"

    br = browser(user_agent=USER_AGENT)
    with closing(br.open(search_url, timeout=timeout)) as response:
        raw = response.read()
    soup = BeautifulSoup(raw, "html5lib")

    extract_indices(soup)

    # Find the rows that represent each book, and skip the first item which is table headers
    trs = soup.select('table[class="table table-striped"] > tbody > tr')

    # map the trs to search results, filter out items that dont have a title or author, and limit it to max_results size
    results = []
    for tr in trs:
        try:
            result = build_search_result(tr, base_url)
            if result.title and result.author:
                results.append(result)
        except Exception as e:
            logger.error(f"Error building search result: {e}")
        if len(results) >= max_results:
            break

    return results[:max_results]

def is_spa_url(url):
    hostname = urllib.parse.urlsplit(url).hostname
    return any(urllib.parse.urlsplit(mirror).hostname == hostname for mirror in SPA_MIRRORS)


def load_json(br, url, timeout, data=None):
    if timeout <= 0:
        raise TimeoutError("Library Genesis request timed out")
    with closing(br.open(url, data=data, timeout=timeout)) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise ValueError("Library Genesis returned an unexpected JSON response")
    return payload


def load_spa_result(br, url, timeout):
    payload = load_json(br, url, timeout)
    if payload.get("isError") is not False or not isinstance(payload.get("result"), dict):
        raise ValueError("Library Genesis API could not complete the request")
    return payload["result"]


def search_spa(query, max_results, timeout, base_url):
    results = []
    seen_ids = set()
    offset = 0
    deadline = time.monotonic() + timeout
    br = browser(user_agent=USER_AGENT)
    while len(results) < max_results:
        params = urllib.parse.urlencode({"query": query, "collection": "libgen", "from": offset})
        search_url = base_url + "/api/search/by-params?" + params
        payload = load_spa_result(br, search_url, deadline - time.monotonic())
        books = payload.get("books")
        if not isinstance(books, list):
            raise ValueError("Library Genesis API did not return a book list")
        total = payload.get("total")
        if not isinstance(total, int) or total < 0:
            raise ValueError("Library Genesis API did not return a result count")
        previous_count = len(seen_ids)
        for book in books:
            try:
                book_id = str(book["id"])
                if not re.fullmatch(r"\d+", book_id) or book_id in seen_ids:
                    continue
                seen_ids.add(book_id)
                result = SearchResult()
                result.title = book["title"].strip()
                authors = book["author"]
                if not isinstance(authors, list):
                    raise ValueError("Library Genesis API did not return an author list")
                result.author = ", ".join(author.strip() for author in authors if author)
                result.formats = book["fileExtension"].strip().upper()
                if not result.title or not result.formats:
                    continue
                year = book.get("year") or ""
                language = book.get("language") or ""
                result.price = "\n".join(str(value) for value in (year, language) if value)
                result.detail_item = base_url + "/book/" + book_id
                result.drm = SearchResult.DRM_UNLOCKED
                results.append(result)
            except (KeyError, TypeError, AttributeError, ValueError) as error:
                logger.warning("Error building API search result: %s", error)
            if len(results) >= max_results:
                break
        offset += len(books)
        if len(seen_ids) == previous_count or offset >= total:
            break
    return results


def resolve_spa_download(search_result, timeout):
    detail_parts = urllib.parse.urlsplit(search_result.detail_item)
    match = re.fullmatch(r"/book/(\d+)", detail_parts.path)
    if not match:
        return False
    book_id = match.group(1)
    base_url = urllib.parse.urlunsplit((detail_parts.scheme, detail_parts.netloc, "", "", ""))
    deadline = time.monotonic() + timeout
    br = browser(user_agent=USER_AGENT)
    try:
        payload = load_spa_result(
            br, base_url + "/api/download/links-by-id?id=" + book_id,
            deadline - time.monotonic(),
        )
        links = payload.get("links")
        if not isinstance(links, list):
            raise ValueError("Library Genesis API did not return download links")
    except Exception as error:
        logger.warning("Could not load book download links: %s", error)
        return False
    for landing_url in links:
        try:
            landing_parts = urllib.parse.urlsplit(landing_url)
            if landing_parts.scheme not in ("http", "https") or not landing_parts.netloc:
                continue
            token = urllib.parse.parse_qs(landing_parts.query).get("l")
            if not token:
                continue
            decrypt_url = urllib.parse.urljoin(
                landing_url, "/api/decrypt?" + urllib.parse.urlencode({"l": token[0]})
            )
            book = load_json(br, decrypt_url, deadline - time.monotonic(), data=b"")
            if str(book.get("id")) != book_id:
                continue
            download_url = urllib.parse.urljoin(landing_url, book["downloadLink"])
            download_parts = urllib.parse.urlsplit(download_url)
            if (
                download_parts.scheme not in ("http", "https")
                or not download_parts.netloc
                or download_parts.path != "/api/download"
                or urllib.parse.parse_qs(download_parts.query).get("id") != [book_id]
            ):
                continue
            image_link = book.get("imageLink")
            if isinstance(image_link, str) and image_link:
                cover_url = urllib.parse.urljoin(landing_url, image_link)
                if urllib.parse.urlsplit(cover_url).scheme in ("http", "https"):
                    search_result.cover_url = cover_url
            search_result.downloads[search_result.formats] = download_url
            return True
        except Exception as error:
            logger.warning("Could not resolve book download: %s", error)
        if time.monotonic() >= deadline:
            break
    return False

# URL check class
def check_spa_api(mirror):
    params = urllib.parse.urlencode(
        {
            "query": "libgen_auto_mirror_healthcheck_no_results",
            "collection": "libgen",
            "from": 0,
        }
    )
    br = browser(user_agent=USER_AGENT)
    payload = load_spa_result(
        br, mirror + "/api/search/by-params?" + params, timeout=5
    )
    books = payload.get("books")
    total = payload.get("total")
    return (
        isinstance(books, list)
        and isinstance(total, int)
        and not isinstance(total, bool)
        and total >= 0
    )


def check_url(mirrors):
    spa_mirrors = [mirror for mirror in mirrors if is_spa_url(mirror)]
    legacy_mirrors = [mirror for mirror in mirrors if not is_spa_url(mirror)]

    for mirror in spa_mirrors:
        try:
            if check_spa_api(mirror):
                return mirror
        except Exception:
            continue

    for mirror in legacy_mirrors:
        try:
            with urlopen(mirror, timeout=5) as response:
                if response.code == 200:
                    return mirror
        except Exception:
            continue

def extract_indices(soup):
    elements = ["Author(s)", "Year", "Pages", "Size", "Ext", "Mirrors"]
    indices = {}

    for idx, th in enumerate(soup.find_all("th")):
        for element in elements:
            if element in th.get_text():
                indices[element] = idx

    global author_index, year_index, pages_index, size_index, ext_index, mirrors_index, title_index, image_index

    image_index = 0
    title_index = 1
    author_index = indices.get("Author(s)")
    year_index = indices.get("Year")
    pages_index = indices.get("Pages")
    size_index = indices.get("Size")
    ext_index = indices.get("Ext")
    mirrors_index = indices.get("Mirrors")


def transform_download_url(url):
    # Pattern for the first format: /ads23875abc (where abc can be letters and numbers)
    pattern1 = re.compile(r"/ads([a-fA-F0-9]+)")
    # Pattern for the second format: /ads.php?md5=235798237abc (where abc can be letters and numbers)
    pattern2 = re.compile(r"/ads\.php\?md5=([a-fA-F0-9]+)")

    # Check and transform the first format
    match1 = pattern1.match(url)
    if match1:
        return f"/get.php?md5={match1.group(1)}"

    # Check and transform the second format
    match2 = pattern2.match(url)
    if match2:
        return f"/get.php?md5={match2.group(1)}"

    # If no match, return the original URL
    return url


def build_search_result(tr, base_url):
    tds = tr.find_all("td")
    s = SearchResult()

    # Extracting all text from title cell
    title_td = tds[title_index]
    all_text = title_td.get_text(separator='\n', strip=True)
    text_parts = [part.strip() for part in all_text.split('\n') if part.strip()]

    # Remove duplicates
    unique_parts = []
    for part in text_parts:
        if part not in unique_parts:
            unique_parts.append(part)

    # Join all parts with " - "
    s.title = " - ".join(unique_parts)

    # Extracting the author
    s.author = tds[author_index].text.strip()

    # Extracting size, pages, and year
    size = tds[size_index].text.strip()
    pages = tds[pages_index].text.strip()
    year = tds[year_index].text.strip()

    if pages == "0 pages":
        s.price = f"{size}\n{year}"
    else:
        s.price = f"{size}\n{pages} pages\n{year}"

    # Extracting formats
    s.formats = tds[ext_index].text.strip().upper()

    # Extracting the details URL
    first_link_in_last_td = tds[mirrors_index].find("a", href=True)

    # Details url:
    try:
        detail_url = first_link_in_last_td["href"].replace(
            "get.php", "ads.php"
        )
        detail_parts = urllib.parse.urlsplit(detail_url)
        base_parts = urllib.parse.urlsplit(base_url)
        detail_path = detail_parts.path
        if not detail_path.startswith("/"):
            detail_path = "/" + detail_path
        s.detail_item = urllib.parse.urlunsplit(
            (
                base_parts.scheme,
                base_parts.netloc,
                detail_path,
                detail_parts.query,
                detail_parts.fragment,
            )
        )
    except:
        s.detail_item = None

    # Setting DRM status
    s.drm = SearchResult.DRM_UNLOCKED

    # Extracting image
    try:
        image_src = tds[image_index].find("img").get("src")
    except:
        image_src = None
        logger.exception("Error extracting image src")

    if image_src:
        s.cover_url = base_url + image_src

    return s


class LibgenConfigWidget(BasicStoreConfigWidget):
    def __init__(self, store):
        super().__init__(store)
        self.mirror = QComboBox(self)
        self.mirror.addItem("Auto-detect supported mirror", AUTO_MIRROR)
        for mirror in LIBGEN_MIRRORS:
            hostname = urllib.parse.urlparse(mirror).hostname
            self.mirror.addItem(hostname, mirror)

        selected_mirror = store.config.get("mirror", AUTO_MIRROR)
        selected_index = self.mirror.findData(selected_mirror)
        self.mirror.setCurrentIndex(selected_index if selected_index >= 0 else 0)

        row = self.gridLayout.rowCount()
        self.gridLayout.addWidget(QLabel("Mirror:", self), row, 0)
        self.gridLayout.addWidget(self.mirror, row, 1)


class LibgenStorePlugin(BasicStoreConfig, StorePlugin):
    def __init__(self, *args, **kwargs):
        StorePlugin.__init__(self, *args, **kwargs)
        selected_mirror = self.config.get("mirror", AUTO_MIRROR)
        self.libgen_url = (
            selected_mirror
            if selected_mirror in LIBGEN_MIRRORS
            else check_url(LIBGEN_MIRRORS)
        )

    def config_widget(self):
        return LibgenConfigWidget(self)

    def save_settings(self, config_widget):
        BasicStoreConfig.save_settings(self, config_widget)
        selected_mirror = config_widget.mirror.currentData()
        self.config["mirror"] = selected_mirror
        self.libgen_url = (
            selected_mirror
            if selected_mirror in LIBGEN_MIRRORS
            else check_url(LIBGEN_MIRRORS)
        )

    def open(self, parent=None, detail_item=None, external=False):
        url = self.libgen_url

        if external or self.config.get("open_external", False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get("tags", ""))
            d.exec_()

    @staticmethod
    def get_details(search_result, timeout=60, retries=3):
        if is_spa_url(search_result.detail_item):
            return resolve_spa_download(search_result, timeout)
        s = search_result
        br = browser(user_agent=USER_AGENT)
        deadline = time.monotonic() + timeout
        raw = None
        for attempt in range(retries):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                with closing(br.open(s.detail_item, timeout=remaining)) as response:
                    raw = response.read()
                break
            except Exception as error:
                logger.info("Could not load %s: %s", s.detail_item, error)
                # server error, retry after delay
                if attempt + 1 < retries:
                    time.sleep(min(1, max(0, deadline - time.monotonic())))

        if raw is None:
            return False

        soup2 = BeautifulSoup(raw, "html5lib")
        # Select the first <a> tag inside the div with id="download"
        download_a = soup2.select_one('a[href*="get.php"]')
        if download_a:
            download_url = download_a.get("href")
        else:
            # Handle the case where the download link is not found
            download_url = None

        if not download_url:
            return False
        s.downloads[s.formats] = urllib.parse.urljoin(s.detail_item, download_url)
        return True

    def search(self, query, max_results=10, timeout=60):
        for result in search_libgen(
            query, max_results=max_results, timeout=timeout, base_url=self.libgen_url
        ):
            yield result

if __name__ == "__main__":
    query_string = " ".join(sys.argv[1:])
    for result in search_libgen(query_string):
        print(result)
