from datasets import load_dataset
import ffn
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.metrics import confusion_matrix


def main():
    signals_df = pd.DataFrame(
        load_dataset("edarchimbaud/signals-monthly-sp500", split="train")
    )
    targets_df = pd.DataFrame(
        load_dataset("edarchimbaud/targets-monthly-sp500", split="train")
    )
    print(signals_df.iloc[0, :])
    print(targets_df.iloc[0, :])

    # merging the two dataframes on the 'symbol' and 'date' columns
    merged_df = pd.merge(signals_df, targets_df, on=["symbol", "date"])
    merged_df.set_index(["symbol", "date"], inplace=True)

    # filter the merged dataframe to include only "*quintile" columns from the first dataset
    quintile_cols = [
        col
        for col in merged_df.columns
        if "quintile" in col and col != "return_quintile"
    ]
    X = merged_df[quintile_cols]

    # target variable is 'return_quintile' from the second dataset
    y = merged_df[["return_quintile", "return"]]

    # split the data into training and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.5, random_state=42
    )

    # use a random forest classifier
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_train, y_train.return_quintile)

    # Predict the 'return_quintile' for the test set
    y_pred = clf.predict(X_test)

    # Calculate metrics
    accuracy = accuracy_score(y_test.return_quintile, y_pred)
    precision = precision_score(
        y_test.return_quintile, y_pred, average="weighted"
    )  # you can choose another averaging method if you prefer
    recall = recall_score(y_test.return_quintile, y_pred, average="weighted")
    f1 = f1_score(y_test.return_quintile, y_pred, average="weighted")

    # Print metrics
    print(f"Accuracy: {accuracy}")
    print(f"Precision: {precision}")
    print(f"Recall: {recall}")
    print(f"F1 Score: {f1}")

    # Confusion matrix
    cm = confusion_matrix(y_test.return_quintile, y_pred)
    plt.figure(figsize=(10, 7))
    sns.heatmap(cm, annot=True, fmt="d")
    plt.xlabel("Predicted")
    plt.ylabel("Truth")
    plt.show()

    # Plot cumulative returns
    fig = plt.figure(figsize=(10, 7))
    for n in range(5):
        y_test.loc[y_pred == n, "return"].groupby("date").mean().cumsum().plot()
    plt.legend([f"Predicted {n}" for n in range(5)])
    plt.show()

    # Plot cumulative returns for long and short positions
    fig = plt.figure(figsize=(10, 7))
    df = pd.concat(
        [
            y_test.loc[y_pred == 4, "return"].groupby("date").mean(),
            y_test.loc[y_pred == 1, "return"].groupby("date").mean(),
        ],
        axis=1,
        keys=["long", "short"],
    )
    df = df.fillna(0)
    df["return"] = df["long"] - df["short"]
    df["return"].cumsum().plot()
    plt.show()

    # Display performance metrics
    nav = (df["return"] + 1).cumprod()
    stats = nav.calc_stats()
    stats.display()


if __name__ == "__main__":
    main()
