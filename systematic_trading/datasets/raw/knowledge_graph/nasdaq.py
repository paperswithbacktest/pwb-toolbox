"""
curl -C - -O "https://dumps.wikimedia.org/enwiki/20230620/enwiki-20230620-pages-articles-multistream.xml.bz2"
curl -C - -O "https://dumps.wikimedia.org/enwiki/20230620/enwiki-20230620-pages-articles-multistream-index.txt.bz2"
"""

import os
import time
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
import click
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm
from webdriver_manager.chrome import ChromeDriverManager

from systematic_trading.helpers import nasdaq_headers
from systematic_trading.datasets.raw.knowledge_graph.wikipedia import wikipedia


class Nasdaq:
    def __init__(self):
        pass

    def download(self):
        """
        Returns a DataFrame of NASDAQ stocks
        """
        path_tgt = os.path.join("data", "nasdaq-stocks.raw.csv")
        if os.path.exists(path_tgt):
            return
        url = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&download=true"
        response = requests.get(url, headers=nasdaq_headers())
        json_data = response.json()
        self._df = pd.DataFrame(data=json_data["data"]["rows"])
        self._df = self._df[["symbol", "name", "country", "sector", "industry"]]
        # filter common stocks
        index = df.name.apply(lambda x: x.endswith("Common Stock"))
        self._df = self._df.loc[index, :]
        self._df.reset_index(drop=True, inplace=True)
        nasdaq_names = self._df.name.apply(
            lambda x: x.replace(" Common Stock", "")
            .replace(" Inc.", "")
            .replace(" Inc", "")
            .replace(" Class A", "")
        )
        self._df.name = nasdaq_names
        # Match with straight equality
        pages_dict = parse_wikipedia_company_pages()
        wikipedia_names = [n.replace(" (company)", "") for n in pages_dict.keys()]
        self._df["wikipediaTitle"] = ""
        for index, row in self._df.iterrows():
            if nasdaq_names[index] in wikipedia_names:
                self._df.loc[index, "wikipediaTitle"] = nasdaq_names[index]
        self.__save(path=path_tgt)

    def __load(self, path):
        self._df = pd.read_csv(path)

    def __save(self, path):
        self._df.to_csv(
            path,
            index=False,
        )

    def add_argument_wikipedia_title(self):
        path_src = os.path.join("data", "nasdaq-stocks.raw.csv")
        path_tgt = os.path.join("data", "nasdaq-stocks.title.csv")
        self._df = self.__load(path=path_src)
        self._df.fillna("", inplace=True)

        # Match with Google search
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
        }
        options = Options()
        options.headless = False
        options.add_argument("user-agent=" + headers["User-Agent"])
        driver = webdriver.Chrome(ChromeDriverManager().install(), options=options)
        driver.get("https://www.google.com/")
        input("Cookies accepted?")
        path = os.path.join("data", "nasdaq-stocks.csv")
        for index, row in tqdm(self._df.iterrows(), total=len(self._df)):
            if index < 6:
                continue
            if row["wikipediaTitle"]:
                continue
            encoded_query = quote_plus(row["name"])
            url = "https://www.google.com/search?hl=en&q=" + encoded_query
            driver.get(url)
            time.sleep(60)
            body = driver.find_element("xpath", "//body")
            body_html = body.get_attribute("innerHTML")
            soup = BeautifulSoup(body_html, "html.parser")
            hrefs = [
                a["href"]
                for a in soup.find_all("a")
                if a.has_attr("href")
                and a["href"].startswith("https://en.wikipedia.org/")
                and a.text.strip() == "Wikipedia"
            ]
            if len(hrefs) == 0:
                continue
            href = hrefs[0]
            wikipedia_name = href.split("/")[-1].replace("_", " ")
            self._df.loc[index, "wikipediaTitle"] = wikipedia_name
            self.__save(path=path_tgt)
        self.__save(path=path_tgt)

    def add_wikipedia_page():
        self._df = self.__load(
            path=os.path.join("data", "nasdaq-stocks.title.csv"),
        )
        titles = self._df.wikipediaTitle.tolist()
        wikipedia = Wikipedia()
        wikipedia.select_pages(titles)
