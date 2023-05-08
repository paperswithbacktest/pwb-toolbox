import os

from kili.client import Kili
import requests
from bs4 import BeautifulSoup


class SsrnPaper:
    def __init__(self, abstract_id: int):
        self.abstract_id = abstract_id
        self._external_id = str(abstract_id)
        self.pdf_path = None
        self.url = (
            f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={self.abstract_id}"
        )
        self._kili_client = Kili(api_key=os.getenv("KILI_API_KEY"))

    def exists_in_kili(self, project_id: str):
        assets = self._kili_client.assets(
            project_id=project_id,
            external_id_strictly_in=[self._external_id],
            fields=["id"],
            disable_tqdm=True,
        )
        return len(assets) == 1

    def from_ssrn(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
        }
        html = requests.get(self.url, headers=headers).content
        soup = BeautifulSoup(html, "html.parser")
        hrefs = [
            tag["href"]
            for tag in soup.find_all("a")
            if tag.has_attr("href") and tag["href"].startswith("Delivery.cfm/")
        ]
        if len(hrefs) == 0:
            return
        pdf_url = "https://papers.ssrn.com/sol3/" + hrefs[0]
        folder = os.path.join(os.getenv("HOME"), "Downloads")
        filename = f"{self.abstract_id}.pdf"
        self.pdf_path = os.path.join(folder, filename)
        response = requests.get(pdf_url, headers={**headers, "Referer": self.url})
        with open(self.pdf_path, "wb") as handler:
            handler.write(response.content)

    def to_kili(self, project_id: str, metadata: dict = {}):
        self._kili_client.append_many_to_dataset(
            project_id=project_id,
            content_array=[self.pdf_path],
            external_id_array=[self._external_id],
            disable_tqdm=True,
            json_metadata_array=[metadata],
        )
