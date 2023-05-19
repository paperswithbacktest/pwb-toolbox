"""
Revenue estimate data.
"""
from dataset import Dataset
import pandas as pd


class RevenueEstimate(Dataset):
    """
    Revenue estimate data.
    """

    def __init__(self):
        super().__init__()
        self.expected_columns = [
            "symbol",
            "date",
            "current_qtr",
            "no_of_analysts_current_qtr",
            "next_qtr",
            "no_of_analysts_next_qtr",
            "current_year",
            "no_of_analysts_current_year",
            "next_year",
            "no_of_analysts_next_year",
            "avg_estimate_current_qtr",
            "avg_estimate_next_qtr",
            "avg_estimate_current_year",
            "avg_estimate_next_year",
            "low_estimate_current_qtr",
            "low_estimate_next_qtr",
            "low_estimate_current_year",
            "low_estimate_next_year",
            "high_estimate_current_qtr",
            "high_estimate_next_qtr",
            "high_estimate_current_year",
            "high_estimate_next_year",
            "year_ago_sales_current_qtr",
            "year_ago_sales_next_qtr",
            "year_ago_sales_current_year",
            "year_ago_sales_next_year",
            "sales_growth_yearest_current_qtr",
            "sales_growth_yearest_next_qtr",
            "sales_growth_yearest_current_year",
            "sales_growth_yearest_next_year",
        ]
        self.data = pd.DataFrame(columns=self.expected_columns)
