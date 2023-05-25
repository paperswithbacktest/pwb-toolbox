"""
SSRN Paper Summarizer.
"""
import os
import json
from pprint import pprint

from kili.client import Kili
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain.chat_models import ChatOpenAI
from tqdm import tqdm

from systematic_trading.strategy_ideas.ssrn_abstract import SsrnAbstract
from systematic_trading.strategy_ideas.ssrn_strategy import SsrnStrategy


class SsrnPaperSummarizer:
    """
    SSRN Paper Summarizer.
    """

    def __init__(self):
        self._kili_client = Kili(api_key=os.getenv("KILI_API_KEY"))
        self._openai_client = ChatOpenAI(
            model_name="gpt-3.5-turbo",
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0,
        )

    def __parse_label(self, asset):
        label = asset["labels"][-1]["jsonResponse"]
        is_strategy = label["IS_STRATEGY"]["categories"][0]["name"]
        key_elements_annotations = label["KEY_ELEMENTS"]["annotations"]
        key_elements = []
        for annotation in key_elements_annotations:
            key_elements.append(
                {
                    "category": annotation["categories"][0]["name"],
                    "content": annotation["content"],
                    "page_number": min(annotation["annotations"][0]["pageNumberArray"]),
                }
            )
        key_elements = sorted(key_elements, key=lambda x: x["page_number"])
        aggregated_key_elements = {}
        for item in key_elements:
            category = item["category"]
            content = item["content"]
            if category in aggregated_key_elements:
                aggregated_key_elements[category].append(content)
            else:
                aggregated_key_elements[category] = [content]
        return aggregated_key_elements, is_strategy

    def __query_chatgpt(self, instructions: str, text: str):
        system_message_prompt = SystemMessagePromptTemplate.from_template(instructions)
        human_template = "{text}"
        human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
        chat_prompt = ChatPromptTemplate.from_messages(
            [system_message_prompt, human_message_prompt]
        )
        response = self._openai_client(
            chat_prompt.format_prompt(
                text=text,
            ).to_messages()
        )
        return response.content

    def __predict_trading_rules(self, key_elements):
        trading_rules = " ".join(key_elements.get("TRADING_RULES", []))
        if trading_rules == "":
            return ""
        instructions = """You are a helpful assistant that extract the rules of the following trading strategy as bullet points.
Here is an example:
- Investment universe: 54 countries' 10-year government bonds
- Sort assets into quintiles based on past month return
- Long top quintile assets (highest returns from previous month)
- Short bottom quintile assets (lowest returns from previous month)
- Utilize equal weighting for assets
- Rebalance strategy on a monthly basis"""
        return self.__query_chatgpt(instructions=instructions, text=trading_rules)

    def __predict_backtrader(self, key_elements):
        trading_rules = " ".join(key_elements.get("TRADING_RULES", []))
        if trading_rules == "":
            return ""
        instructions = (
            "Write the python code with Backtrader for the following strategy."
        )
        return self.__query_chatgpt(instructions=instructions, text=trading_rules)

    def __predict_markets_traded(self, key_elements):
        markets_traded = " ".join(key_elements.get("MARKETS_TRADED", []))
        if markets_traded == "":
            return ""
        instructions = (
            "Extract the list of markets traded."
            " It can be one or more of the following: equities, bonds, bills, commodities, currencies, cryptos."
        )
        return self.__query_chatgpt(instructions=instructions, text=markets_traded)

    def __predict_period_of_rebalancing(self, key_elements):
        period_of_rebalancing = " ".join(key_elements.get("PERIOD_OF_REBALANCING", []))
        if period_of_rebalancing == "":
            return ""
        instructions = "Extract the period of rebalancing. It can be: daily, weekly, quarterly, yearly."
        return self.__query_chatgpt(
            instructions=instructions, text=period_of_rebalancing
        )

    def __predict_backtest_period(self, key_elements):
        backtest_period = " ".join(key_elements.get("BACKTEST_PERIOD", []))
        if backtest_period == "":
            return ""
        instructions = "Extract the backtest_period. Example: 1961-2018."
        return self.__query_chatgpt(instructions=instructions, text=backtest_period)

    def __format_percent(self, text):
        if "%" not in text:
            return f"{text}%"
        return text

    def predict(self, kili_project_id: str, target_folder: str):
        """
        Run predictions.
        """
        assets = self._kili_client.assets(
            project_id=kili_project_id,
            fields=["id", "externalId", "labels.jsonResponse"],
            status_in=["LABELED"],
            disable_tqdm=True,
        )
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)
        for asset in tqdm(assets):
            key_elements, is_strategy = self.__parse_label(asset)
            if is_strategy == "NO":
                continue
            abstract_id = int(asset["externalId"])
            path = os.path.join(target_folder, f"{abstract_id}.md")
            if os.path.exists(path):
                continue
            abstract = SsrnAbstract(abstract_id)
            abstract.from_ssrn()
            strategy = SsrnStrategy(abstract)
            strategy.trading_rules = self.__predict_trading_rules(key_elements)
            strategy.backtrader = self.__predict_backtrader(key_elements)
            strategy.markets_traded = self.__predict_markets_traded(key_elements)
            strategy.period_of_rebalancing = self.__predict_period_of_rebalancing(
                key_elements
            )
            strategy.backtest_period = self.__predict_backtest_period(key_elements)
            annual_return = " ".join(key_elements.get("ANNUAL_RETURN", []))
            strategy.annual_return = self.__format_percent(annual_return)
            maximum_drawdown = " ".join(key_elements.get("MAXIMUM_DRAWDOWN", []))
            strategy.maximum_drawdown = self.__format_percent(maximum_drawdown)
            strategy.sharpe_ratio = " ".join(key_elements.get("SHARPE_RATIO", []))
            annual_standard_deviation = " ".join(
                key_elements.get("ANNUAL_STANDARD_DEVIATION", [])
            )
            strategy.annual_standard_deviation = self.__format_percent(
                annual_standard_deviation
            )
            print(path)
            with open(path, "w", encoding="utf-8") as f:
                markdown = strategy.to_markdown()
                f.write(markdown)
                print(markdown)
