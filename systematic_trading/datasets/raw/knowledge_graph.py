"""
curl -C - -O "https://dumps.wikimedia.org/enwiki/20230620/enwiki-20230620-pages-articles-multistream.xml.bz2"
curl -C - -O "https://dumps.wikimedia.org/enwiki/20230620/enwiki-20230620-pages-articles-multistream-index.txt.bz2"
"""
import bz2
import codecs
import itertools
import os
import pickle
from pprint import pprint
import re
import time
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
import click
import Levenshtein
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from tqdm import tqdm
from webdriver_manager.chrome import ChromeDriverManager

from systematic_trading.helpers import nasdaq_headers

tqdm.pandas()


# def get_categories(text: str):
#     """
#     Extract categories
#     """
#     pattern = r"\[\[Category:(.*?)(?:\||\]\])"
#     matches = re.findall(pattern, text)
#     return matches


@click.command()
@click.option("--mode", default="", help="")
def main(mode):
    if mode == "download":
        download_nasdaq_stocks()
        enrich_nasdaq_stocks_with_google()

    path = os.path.join("data", "nasdaq-stocks.csv")
    nasdaq_df = pd.read_csv(path)
    nasdaq_df.fillna("", inplace=True)
    print(nasdaq_df.columns)

    company_pages_dict = parse_wikipedia_company_pages()

    for _, row in nasdaq_df.iterrows():
        if row["wikipedia"] == "":
            continue
        if row["wikipedia"] not in company_pages_dict.keys():
            print(row["wikipedia"])


if __name__ == "__main__":
    main()
