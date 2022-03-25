# -*- coding: utf-8 -*-
# License: GPLv3 Copyright: 2021, winnbyte
from __future__ import absolute_import, division, print_function, unicode_literals

import urllib.parse
import time

from bs4 import BeautifulSoup

from PyQt5.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.web_store_dialog import WebStoreDialog

BASE_URL = "https://libgen.is"
USER_AGENT = "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko"

#####################################################################
# Plug-in base class
#####################################################################


def search_libgen(query, max_results=10, timeout=60):
    res = "25" if max_results <= 25 else "50" if max_results <= 50 else "100"
    search_url = f"{BASE_URL}/search.php?req={query.decode()}&res={res}&view=simple"
    print("searching: " + search_url)
    print("max results: " + str(max_results))
    br = browser(user_agent=USER_AGENT)
    raw = br.open(search_url).read()
    soup = BeautifulSoup(raw, "html5lib")

    trs = soup.select('table[class="c"] > tbody > tr')
    count = 0
    for item in trs:
        index = trs.index(item)
        if count == max_results:
            break

        if index == 0:
            continue

        tds = item.select("td")

        title = tds[2].select("a")[-1].text
        detail_url = BASE_URL + "/" + tds[2].select("a")[-1].get("href")

        libgen_id = int(tds[0].text)
        author = tds[1].text
        series = tds[2].select("a")[0].text if len(tds[2].select("a")) > 1 else None
        publisher = tds[3].text
        year = tds[4].text
        pages = tds[5].text
        language = tds[6].text
        size = tds[7].text
        extension = tds[8].text.upper()
        mirror1_url = tds[9].select("a")[0].get("href")

        if title and author:
            s = LibgenSearchResult(libgen_id)
            s.title = title
            s.author = author
            s.price = f"{size}\n{pages} pages\n{year}"  # use price column to display more info
            s.detail_item = detail_url
            s.formats = extension
            s.drm = SearchResult.DRM_UNLOCKED
            s.mirror1_url = mirror1_url
            count += 1
            yield s


class LibgenStorePlugin(BasicStoreConfig, StorePlugin):
    def open(self, parent=None, detail_item=None, external=False):
        url = BASE_URL

        if external or self.config.get("open_external", False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get("tags", ""))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        for result in search_libgen(query, max_results=max_results, timeout=timeout):
            yield result

    def get_details(self, search_result, timeout):
        s = search_result
        br = browser(user_agent=USER_AGENT)
        while True:
            try:
                raw = br.open(s.mirror1_url).read()
                break
            except:
                # sever error, retry after delay
                time.sleep(0.1)

        soup2 = BeautifulSoup(raw, "html5lib")
        download_a = soup2.select('div[id="download"] > ul > li > a')[0]
        download_url = download_a.get("href")

        new_base_url = urllib.parse.urlparse(s.mirror1_url).hostname
        image_url = "http://" + new_base_url + soup2.select("img")[0].get("src")

        s.downloads[s.formats] = download_url
        s.cover_url = image_url


class LibgenSearchResult(SearchResult):
    def __init__(self, id):
        super().__init__()
        self.id = id

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)


if __name__ == "__main__":
    for result in search_libgen(bytes(" ".join(sys.argv[1:]), "utf-8")):
        print(result)
