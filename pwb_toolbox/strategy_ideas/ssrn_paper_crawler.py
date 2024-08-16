from collections import Counter
import os
import re
import time
from typing import Optional

from bs4 import BeautifulSoup
from kili.client import Kili
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import textract
from tqdm import tqdm
from webdriver_manager.chrome import ChromeDriverManager

from systematic_trading.strategy_ideas.ssrn_paper import SsrnPaper


class SsrnPaperCrawler:
    def __init__(
        self,
        project_id: Optional[str] = None,
    ):
        self.tgt_kili_project_id = tgt_kili_project_id

    def __from_url(self, url: str):
        return int(url.split("=")[-1])

    def from_kili(self, src_kili_project_id: str):
        """
        List all abstract ids from Kili
        """
        kili_client = Kili(api_key=os.getenv("KILI_API_KEY"))
        assets = kili_client.assets(
            project_id=src_kili_project_id,
            fields=["externalId", "labels.jsonResponse", "labels.labelType"],
            disable_tqdm=True,
        )
        for asset in assets:
            labels = [
                label
                for label in asset["labels"]
                if label["labelType"] in ["DEFAULT", "REVIEW"]
            ]
            if len(labels) == 0:
                continue
            is_strategy = labels[-1]["jsonResponse"]["IS_STRATEGY"]["categories"][0][
                "name"
            ]
            if is_strategy != "Yes":
                continue
            abstract_id = int(asset["externalId"])
            paper = SsrnPaper(abstract_id)
            if paper.exists_in_kili(self.tgt_kili_project_id):
                continue
            paper.from_ssrn()
            if paper.pdf_path is None:
                continue
            paper.to_kili(self.tgt_kili_project_id, metadata={"text": filename})
