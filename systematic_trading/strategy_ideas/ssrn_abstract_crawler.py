from collections import Counter
import os
import re
import time
from typing import Optional

from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import textract
from tqdm import tqdm
from webdriver_manager.chrome import ChromeDriverManager

from ssrn_abstract import SsrnAbstract


class SsrnAbstractCrawler:
    def __init__(
        self,
        kili_project_id: Optional[str] = None,
        is_strategy: Optional[str] = None,
    ):
        self.kili_project_id = kili_project_id
        self.is_strategy = is_strategy
        self._driver = None

    def __from_url(self, url: str):
        return int(url.split("=")[-1])

    def __download_and_save_to_kili(self, abstract_ids: list):
        for abstract_id in tqdm(abstract_ids):
            abstract = SsrnAbstract(abstract_id)
            if (
                abstract.exists_in_kili(self.kili_project_id)
                or not abstract.exists_in_ssrn()
            ):
                continue
            abstract.from_ssrn()
            if self.is_strategy is not None:
                abstract.is_strategy = self.is_strategy
            abstract.to_kili(self.kili_project_id)

    def __go_to_page(self, page: int):
        self._driver.find_element(
            "xpath", '//input[@aria-label="Go to page"]'
        ).send_keys(page)
        self._driver.find_element("xpath", '//button[@aria-label="Go"]').click()

    def from_jel_code(self, jel_code: str, from_page: int = 1):
        """
        List all abstract ids from SSRN
        """
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
        }
        options = Options()
        options.headless = True
        options.add_argument("user-agent=" + headers["User-Agent"])
        self._driver = webdriver.Chrome(
            ChromeDriverManager().install(), options=options
        )
        self._driver.get("https://papers.ssrn.com/sol3/DisplayAbstractSearch.cfm")
        self._driver.find_element_by_id("onetrust-accept-btn-handler").click()
        self._driver.find_element_by_id("advanced_search").send_keys(jel_code)
        self._driver.find_element_by_id("srchCrit2").find_element_by_xpath("..").click()
        self._driver.find_element(
            "xpath", '//button[contains(@class, "primary")]'
        ).click()
        for page in range(from_page, 200 + 1):
            self.__go_to_page(page)
            print(f"{page} / 200")
            body = self._driver.find_element("xpath", "//body")
            body_html = body.get_attribute("innerHTML")
            soup = BeautifulSoup(body_html, "html.parser")
            a_tags = soup.find_all("a", {"class": "title optClickTitle"})
            abstract_ids = [self.__from_url(a_tag["href"]) for a_tag in a_tags]
            abstract_ids = list(set(abstract_ids))
            time.sleep(10)
            self.__download_and_save_to_kili(abstract_ids)
