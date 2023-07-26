"""
curl -C - -O "https://dumps.wikimedia.org/enwiki/20230620/enwiki-20230620-pages-articles-multistream.xml.bz2"
curl -C - -O "https://dumps.wikimedia.org/enwiki/20230620/enwiki-20230620-pages-articles-multistream-index.txt.bz2"
"""
import bz2
import os
import pickle
import re

from bs4 import BeautifulSoup
import click
from tqdm import tqdm


DRIVE = "/Users/edba/Downloads"


class Wikipedia:
    def __init__(self):
        path = os.path.join(
            DRIVE,
            "Raw",
            "Wikipedia",
            "enwiki-20230620-pages-articles-multistream.xml.bz2",
        )
        self.handler = bz2.BZ2File(path, "r")

    def __del__(self):
        self.handler.close()

    def select_pages(self, titles: list[str]):
        """
        Returns the Wikipedia pages of companies that are traded.
        """
        pages = {}
        for line in tqdm(self.handler, total=22962775):
            line = line.decode("utf-8")
            if "<page>" in line:
                page_content = []
                page_content.append(line)
                while "</page>" not in line:
                    line = next(self.handler).decode("utf-8")
                    page_content.append(line)
                page = "".join(page_content).strip()
                soup = BeautifulSoup(page, "xml")
                title_tag = soup.find("title")
                title = title_tag.get_text()
                if title in titles:
                    text_tag = soup.find("text")
                    text = text_tag.get_text()
                    pages[title] = text
        return pages
