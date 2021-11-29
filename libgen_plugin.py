# -*- coding: utf-8 -*-
# License: GPLv3 Copyright: 2021, winnbyte
from __future__ import absolute_import, division, print_function, unicode_literals

import urllib.parse

from bs4 import BeautifulSoup

from PyQt5.Qt import QUrl

from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.web_store_dialog import WebStoreDialog

BASE_URL = 'https://libgen.is'
USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko'

#####################################################################
# Plug-in base class
#####################################################################

def search_libgen(query, max_results=10, timeout=60):
    search_url = BASE_URL + '/search.php?req=' + query.decode()
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

        tds = item.select('td')
        detail_url = BASE_URL + "/" + tds[2].select('a')[0].get('href')
        title = tds[2].select('a')[0].text
        author = tds[1].select('a')[0].text
        extension = tds[8].text.upper()

        mirror1_url = tds[9].select('a')[0].get('href')
        raw = br.open(mirror1_url).read()
        soup2 = BeautifulSoup(raw, "html5lib")
        new_base_url = urllib.parse.urlparse(mirror1_url).hostname

        download_a = soup2.select('div[id="download"] > ul > li > a')[0]
        download_url = download_a.get("href")

        image_url = 'http://' + new_base_url + soup2.select('img')[0].get('src')

        if title and author and download_url:
            s = SearchResult()
            s.title = title
            s.author = author
            s.cover_url = image_url
            s.detail_item = detail_url
            s.formats = extension
            s.drm = SearchResult.DRM_UNLOCKED
            s.downloads[extension] = download_url
            count += 1
            yield s


class LibgenStorePlugin(BasicStoreConfig, StorePlugin):
    def open(self, parent=None, detail_item=None, external=False):
        url = BASE_URL

        if external or self.config.get('open_external', False):
            open_url(QUrl(url_slash_cleaner(detail_item if detail_item else url)))
        else:
            d = WebStoreDialog(self.gui, url, parent, detail_item)
            d.setWindowTitle(self.name)
            d.set_tags(self.config.get('tags', ''))
            d.exec_()

    def search(self, query, max_results=10, timeout=60):
        for result in search_libgen(query, max_results=max_results, timeout=timeout):
            yield result


if __name__ == '__main__':
    for result in search_libgen(bytes(' '.join(sys.argv[1:]), 'utf-8')):
        print(result)
