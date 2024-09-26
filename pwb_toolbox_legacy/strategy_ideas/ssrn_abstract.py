import json
import os
import requests
from bs4 import BeautifulSoup
from kili.client import Kili


class SsrnAbstract:
    def __init__(self, abstract_id: int):
        self.abstract_id = abstract_id
        self.url = (
            f"https://papers.ssrn.com/sol3/papers.cfm?abstract_id={self.abstract_id}"
        )
        self.abstract = ""
        self.authors = []
        self.jel_classification = []
        self.keywords = []
        self.online_date = ""
        self.publication_date = ""
        self.title = ""
        self.is_strategy = ""
        self._kili_client = Kili(api_key=os.getenv("KILI_API_KEY"))
        self._external_id = str(abstract_id)
        self._soup = None

    def __ssrn_page(self):
        if self._soup is not None:
            return self._soup
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"
        }
        response = requests.get(self.url, headers=headers)
        self._soup = BeautifulSoup(response.content, "html.parser")
        return self._soup

    def exists_in_ssrn(self):
        soup = self.__ssrn_page()
        abstract_tag = soup.find("div", {"class": "abstract-text"})
        title = "The submitter of this work did not provide a PDF file for download"
        no_download_tag = soup.find("a", {"title": title})
        return abstract_tag is not None and no_download_tag is None

    def from_ssrn(self):
        soup = self.__ssrn_page()
        # abstract
        abstract_tag = soup.find("div", {"class": "abstract-text"})
        self.abstract = abstract_tag.find("p").text.strip()
        # authors
        author_tags = soup.find_all("meta", {"name": "citation_author"})
        self.authors = [tag["content"] for tag in author_tags]
        # JEL classification
        p_tags = soup.find_all("p")
        pattern = "JEL Classification:"
        jel_tag = [tag for tag in p_tags if pattern in tag.text]
        if len(jel_tag) == 1:
            self.jel_classification = (
                jel_tag[0].text.replace(pattern, "").strip().split(", ")
            )
        # keywords
        keywords_tag = soup.find("meta", {"name": "citation_keywords"})
        self.keywords = keywords_tag["content"].split(", ")
        # online date
        online_date_tag = soup.find("meta", {"name": "citation_online_date"})
        self.online_date = online_date_tag["content"]
        # publication date
        publication_date_tag = soup.find("meta", {"name": "citation_publication_date"})
        self.publication_date = publication_date_tag["content"]
        # title
        title_tag = soup.find("meta", {"name": "citation_title"})
        self.title = title_tag["content"]

    def __find_json_content_element(self, json_obj, target_id: str):
        results = []
        if isinstance(json_obj, dict):
            if json_obj.get("id") == target_id:
                results.append(json_obj)
            for value in json_obj.values():
                if isinstance(value, (dict, list)):
                    results.extend(self.__find_json_content_element(value, target_id))
        elif isinstance(json_obj, list):
            for item in json_obj:
                if isinstance(item, (dict, list)):
                    results.extend(self.__find_json_content_element(item, target_id))
        return results

    def from_kili(self, project_id: str):
        assets = self._kili_client.assets(
            project_id=project_id,
            external_id_strictly_in=[self._external_id],
            fields=["jsonContent", "labels.jsonResponse", "labels.labelType"],
            disable_tqdm=True,
        )
        assert len(assets) == 1
        asset = assets[0]
        asset["jsonContent"] = json.loads(requests.get(asset["jsonContent"]).content)
        # abstract
        abstract_blocks = self.__find_json_content_element(
            asset["jsonContent"], "abstract"
        )
        assert len(abstract_blocks) == 1
        self.abstract = abstract_blocks[0]["text"]
        # authors
        authors_blocks = self.__find_json_content_element(
            asset["jsonContent"], "authors"
        )
        assert len(authors_blocks) == 1
        self.authors = authors_blocks[0]["text"].split(" | ")
        # JEL classification
        jel_classification_blocks = self.__find_json_content_element(
            asset["jsonContent"], "jel-classification"
        )
        assert len(jel_classification_blocks) == 1
        self.jel_classification = jel_classification_blocks[0]["text"].split(" | ")
        # keywords
        keywords_blocks = self.__find_json_content_element(
            asset["jsonContent"], "keywords"
        )
        assert len(keywords_blocks) == 1
        self.keywords = keywords_blocks[0]["text"].split(" | ")
        # online date
        online_date_blocks = self.__find_json_content_element(
            asset["jsonContent"], "online-date"
        )
        assert len(online_date_blocks) == 1
        self.online_date = online_date_blocks[0]["text"]
        # publication date
        publication_date_blocks = self.__find_json_content_element(
            asset["jsonContent"], "publication-date"
        )
        assert len(publication_date_blocks) == 1
        self.publication_date = publication_date_blocks[0]["text"]
        # title
        title_blocks = self.__find_json_content_element(asset["jsonContent"], "title")
        assert len(title_blocks) == 1
        self.title = title_blocks[0]["text"]
        labels = [
            label
            for label in asset["labels"]
            if label["labelType"] in ["DEFAULT", "REVIEW"]
        ]
        if len(labels) > 0:
            self.is_strategy = labels[-1]["jsonResponse"]["IS_STRATEGY"]["categories"][
                0
            ]["name"]

    def __json_content_children(self, tag_id: str, title: str, text: str):
        return [
            {
                "type": "h3",
                "children": [
                    {
                        "id": f"{tag_id}-h",
                        "text": title,
                    }
                ],
            },
            {
                "type": "p",
                "children": [
                    {
                        "id": tag_id,
                        "text": text,
                    }
                ],
            },
        ]

    def exists_in_folder(self, path: str):
        return os.path.exists(os.path.join(path, f"{self._external_id}.json"))

    def exists_in_kili(self, project_id: str):
        assets = self._kili_client.assets(
            project_id=project_id,
            external_id_strictly_in=[self._external_id],
            fields=["id"],
            disable_tqdm=True,
        )
        return len(assets) == 1

    def to_folder(self, path: str):
        with open(os.path.join(path, f"{self._external_id}.json"), "w") as f:
            json.dump(self.__dict__(), f, indent=4, sort_keys=True)

    def to_kili(self, project_id: str):
        children = (
            self.__json_content_children(
                tag_id="title",
                title="Title",
                text=self.title,
            )
            + self.__json_content_children(
                tag_id="abstract",
                title="Abstract",
                text=self.abstract,
            )
            + self.__json_content_children(
                tag_id="keywords",
                title="Keywords",
                text=" | ".join(self.keywords),
            )
            + self.__json_content_children(
                tag_id="jel-classification",
                title="JEL classification",
                text=" | ".join(self.jel_classification),
            )
            + self.__json_content_children(
                tag_id="authors",
                title="Authors",
                text=" | ".join(self.authors),
            )
            + self.__json_content_children(
                tag_id="url",
                title="Url",
                text=self.url,
            )
            + self.__json_content_children(
                tag_id="publication-date",
                title="Publication date",
                text=self.publication_date,
            )
            + self.__json_content_children(
                tag_id="online-date",
                title="Online date",
                text=self.online_date,
            )
        )
        json_content = [
            {
                "children": children,
            }
        ]
        self._kili_client.append_many_to_dataset(
            project_id=project_id,
            json_content_array=[json_content],
            external_id_array=[self._external_id],
            disable_tqdm=True,
        )
        if self.is_strategy != "":
            json_response = {
                "IS_STRATEGY": {"categories": [{"name": self.is_strategy}]}
            }
            self._kili_client.append_labels(
                project_id=project_id,
                asset_external_id_array=[self._external_id],
                json_response_array=[json_response],
                label_type="DEFAULT",
                disable_tqdm=True,
            )

    def __dict__(self):
        return {
            "abstract": self.abstract,
            "authors": self.authors,
            "external_id": self._external_id,
            "jel_classification": self.jel_classification,
            "keywords": self.keywords,
            "online_date": self.online_date,
            "publication_date": self.publication_date,
            "title": self.title,
            "url": self.url,
        }

    def __str__(self):
        text = "\n\n".join(
            [
                self.title,
                self.abstract,
                " | ".join(self.keywords),
                " | ".join(self.jel_classification),
                " | ".join(self.authors),
            ]
        )
        return text
