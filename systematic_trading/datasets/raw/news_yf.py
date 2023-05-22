"""
News from Yahoo Finance.
"""
from datetime import datetime

from bs4 import BeautifulSoup
from datasets import load_dataset
import pandas as pd
import pytz
import requests
import time
from tqdm import tqdm

from systematic_trading.datasets.raw.news import News
from systematic_trading.helpers import retry_get


class Article:
    """
    Article.
    """

    def __init__(self, url, uuid, title):
        self.url = url
        self.uuid = uuid
        self.title = title
        soup = self.__get_soup(url)
        publisher_tag = soup.find("span", {"class": "caas-attr-provider"})
        self.publisher = publisher_tag.text if publisher_tag is not None else None
        self.publish_time = self.__format_date(
            soup.find("div", {"class": "caas-attr-time-style"}).find("time")[
                "datetime"
            ],
        )
        self.text = soup.find("div", {"class": "caas-body"}).text

    def __format_date(self, date_str):
        """
        Format date.
        """
        date_obj = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        tz = pytz.timezone("GMT")
        date_obj = tz.localize(date_obj)
        return date_obj

    def __get_soup(self, url):
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
        }
        response = retry_get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        return soup

    def to_json(self):
        return {
            "body": self.text,
            "publisher": self.publisher,
            "publish_time": self.publish_time,
            "title": self.title,
            "url": self.url,
            "uuid": self.uuid,
        }


class NewsYF(News):
    """
    News from Yahoo Finance.
    """

    def __init__(self):
        super().__init__()
        self.name = f"news-{self.suffix}"

    def __get_news(self, ticker: str) -> pd.DataFrame:
        """
        Get news for a given ticker.
        """
        url = f"https://finance.yahoo.com/quote/{ticker}/?p={ticker}"
        response = retry_get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        news_tag = soup.find("div", {"id": "quoteNewsStream-0-Stream"})
        data = []
        for h3_tag in news_tag.find_all("h3"):
            a_tag = h3_tag.find("a")
            if not a_tag.has_attr("data-uuid"):
                continue
            article = Article(
                url="https://finance.yahoo.com" + a_tag["href"],
                uuid=a_tag["data-uuid"],
                title=a_tag.text,
            )
            data.append(article.to_json())
        df = pd.DataFrame(data)
        return df

    def download(self):
        """
        Download the news data from Yahoo Finance.
        """
        symbols = self.get_index_symbols()
        frames = []
        for symbol in tqdm(symbols):
            ticker = self.symbol_to_ticker(symbol)
            df = self.__get_news(ticker)
            df["symbol"] = symbol
            # use reindex() to set 'symbol' as the first column
            df = df.reindex(columns=["symbol"] + list(df.columns[:-1]))
            frames.append(df)
            time.sleep(self.sleep_time)
        self.data = pd.concat(frames)
        if self.check_file_exists():
            self.add_previous_data()
        self.data.sort_values(by=["symbol", "publish_time"], inplace=True)
        self.data.reset_index(drop=True, inplace=True)


def main():
    """
    Main function.
    """
    news_yf = NewsYF()
    news_yf.crawl()


if __name__ == "__main__":
    main()
