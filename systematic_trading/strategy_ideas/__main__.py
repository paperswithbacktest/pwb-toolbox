import click

from systematic_trading.strategy_ideas.ssrn_abstract_crawler import SsrnAbstractCrawler
from systematic_trading.strategy_ideas.ssrn_paper_crawler import SsrnPaperCrawler
from systematic_trading.strategy_ideas.ssrn_paper_summary_crawler import (
    SsrnPaperSummaryCrawler,
)


@click.command()
@click.option("--mode")
@click.option("--kili-project-id", help="Kili project id to save the data")
@click.option("--from-page", default=1, help="Starting from 1")
@click.option("--jel-code", default="G14", help="JEL code: G14, G12, G11")
@click.option(
    "--src-kili-project-id", default="", help="Kili project id to read the data"
)
@click.option(
    "--tgt-folder", default="data/summaries", help="Folder to save the summaries"
)
def main(
    mode: str,
    kili_project_id: str,
    from_page: int,
    jel_code: str,
    src_kili_project_id: str,
    target_folder: str,
):
    """
    Main entrypoint of strategy_ideas.
    """
    if mode == "abstract":
        SsrnAbstractCrawler(kili_project_id=kili_project_id).from_jel_code(
            jel_code,
            from_page,
        )
    elif mode == "paper":
        SsrnPaperCrawler(tgt_kili_project_id=kili_project_id).from_kili(
            src_kili_project_id=src_kili_project_id,
        )
    elif mode == "summary":
        ssrn_paper_summarizer = SsrnPaperSummarizer()
        ssrn_paper_summarizer.predict(
            kili_project_id,
            target_folder,
        )


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
