# -*- coding: utf-8 -*-
# License: GPLv3 Copyright: 2024, poochinski9
from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import re
import sys
import time
import urllib.parse

from PyQt5.Qt import QUrl
from bs4 import BeautifulSoup
from calibre import browser, url_slash_cleaner
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.basic_config import BasicStoreConfig
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

BASE_URL = "https://libgen.gs"
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
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


#####################################################################
# Plug-in base class
#####################################################################
def search_libgen(query, max_results=10, timeout=60):
    res = "25" if max_results <= 25 else "50" if max_results <= 50 else "100"
    encoded_query = urllib.parse.quote(query)
    search_url = f"{BASE_URL}/index.php?req={encoded_query}&ext=epub&columns[]=t&columns[]=a&columns[]=s&columns[]=y&columns[]=p&columns[]=i&objects[]=f&objects[]=e&objects[]=s&objects[]=a&objects[]=p&objects[]=w&topics[]=l&topics[]=c&topics[]=f&topics[]=a&topics[]=m&topics[]=r&topics[]=s&res={res}&filesuns=all&covers=on&gmode=on"
    search_url = f"{BASE_URL}/index.php?req={encoded_query}&columns[]=t&columns[]=a&columns[]=s&columns[]=y&columns[]=p&columns[]=i&objects[]=f&objects[]=e&objects[]=s&objects[]=a&objects[]=p&objects[]=w&topics[]=l&topics[]=c&topics[]=f&topics[]=a&topics[]=m&topics[]=r&topics[]=s&res=25&covers=on&gmode=on&filesuns=all"

    br = browser(user_agent=USER_AGENT)
    raw = br.open(search_url).read()
    soup = BeautifulSoup(raw, "html5lib")

    extract_indices(soup)

    # Find the rows that represent each book, and skip the first item which is table headers
    trs = soup.select('table[class="table table-striped"] > tbody > tr')

    # map the trs to search results, filter out items that dont have a title or author, and limit it to max_results size
    results = []
    for tr in trs:
        try:
            result = build_search_result(tr)
            if result.title and result.author:
                results.append(result)
        except Exception as e:
            logger.error(f"Error building search result: {e}")
        if len(results) >= max_results:
            break

    return results[:max_results]


def extract_indices(soup):
    elements = ['Author(s)', 'Year', 'Pages', 'Size', 'Ext', 'Mirrors']
    indices = {}

    for idx, th in enumerate(soup.find_all('th')):
        for element in elements:
            if element in th.get_text():
                indices[element] = idx

    global author_index, year_index, pages_index, size_index, ext_index, mirrors_index, title_index, image_index

    image_index = 0
    title_index = 1
    author_index = indices.get('Author(s)')
    year_index = indices.get('Year')
    pages_index = indices.get('Pages')
    size_index = indices.get('Size')
    ext_index = indices.get('Ext')
    mirrors_index = indices.get('Mirrors')


def transform_download_url(url):
    # Pattern for the first format: /ads23875abc (where abc can be letters and numbers)
    pattern1 = re.compile(r'/ads([a-fA-F0-9]+)')
    # Pattern for the second format: /ads.php?md5=235798237abc (where abc can be letters and numbers)
    pattern2 = re.compile(r'/ads\.php\?md5=([a-fA-F0-9]+)')

    # Check and transform the first format
    match1 = pattern1.match(url)
    if match1:
        return f'/get.php?md5={match1.group(1)}'

    # Check and transform the second format
    match2 = pattern2.match(url)
    if match2:
        return f'/get.php?md5={match2.group(1)}'

    # If no match, return the original URL
    return url


def build_search_result(tr):
    tds = tr.find_all('td')
    s = SearchResult()

    # Extracting the title
    title_links = tds[title_index].find_all("a", href=True)
    s.title = " ".join(link.text.strip() for link in title_links if link.text.strip())

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
        s.detail_item = BASE_URL + first_link_in_last_td["href"].replace("get.php", "ads.php")
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
        s.cover_url = BASE_URL + image_src

    return s


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

    @staticmethod
    def get_details(search_result, retries=3):
        s = search_result
        br = browser(user_agent=USER_AGENT)
        for attempt in range(retries):
            try:
                raw = br.open(s.detail_item).read()
                break
            except:
                logger.info("server error, retrying load of " + s.detail_item)
                # server error, retry after delay
                time.sleep(1)

        soup2 = BeautifulSoup(raw, "html5lib")
        # Select the first <a> tag inside the div with id="download"
        download_a = soup2.select_one('tr a')
        if download_a:
            download_url = download_a.get("href")
        else:
            # Handle the case where the download link is not found
            download_url = None

        new_base_url = urllib.parse.urlparse(s.detail_item).hostname

        s.downloads[s.formats] = "https://" + new_base_url + "/" + download_url

    @staticmethod
    def search(query, max_results=10, timeout=60):
        for result in search_libgen(query, max_results=max_results, timeout=timeout):
            yield result


if __name__ == "__main__":
    query_string = " ".join(sys.argv[1:])
    for result in search_libgen(bytes(" ".join(sys.argv[1:]), "utf-8")):
        print(result)
