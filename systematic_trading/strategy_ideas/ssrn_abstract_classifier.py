import os
import requests

import click
from datasets import Dataset
import evaluate
from kili.client import Kili
import numpy as np
from tqdm import tqdm
from transformers import AutoTokenizer
from transformers import AutoModelForSequenceClassification, TrainingArguments, Trainer
from transformers import DataCollatorWithPadding
from transformers import pipeline

from ssrn_abstract import SsrnAbstract


os.environ["TOKENIZERS_PARALLELISM"] = "false"


class SsrnAbstractClassifier:
    def __init__(self, kili_project_id: str):
        self.kili_client = Kili(api_key=os.getenv("KILI_API_KEY"))
        self.kili_project_id = kili_project_id
        self.zeroshot_author_id = ""
        self.tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased")
        self.id2label = {0: "NO", 1: "YES"}
        self.label2id = {"NO": 0, "YES": 1}
        self.model = AutoModelForSequenceClassification.from_pretrained(
            "distilbert-base-uncased",
            num_labels=2,
            id2label=self.id2label,
            label2id=self.label2id,
        )
        self.data_collator = DataCollatorWithPadding(tokenizer=self.tokenizer)
        self.metric = evaluate.load("f1")
        self.model_name = "ssrn-abstract-classifier"

    def __preprocess_function(self, examples):
        return self.tokenizer(examples["text"], truncation=True)

    def __compute_metrics(self, eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)
        return self.metric.compute(predictions=predictions, references=labels)

    def train(self):
        assets = self.kili_client.assets(
            project_id=self.kili_project_id,
            fields=["id", "externalId", "labels.jsonResponse", "labels.labelType"],
            status_in=["LABELED"],
        )
        labels = []
        texts = []
        for asset in tqdm(assets):
            groundtruth_labels = [
                l for l in asset["labels"] if l["labelType"] == "DEFAULT"
            ]
            if len(groundtruth_labels) == 0:
                continue
            groundtruth_category = groundtruth_labels[-1]["jsonResponse"][
                "IS_STRATEGY"
            ]["categories"][0]["name"]
            labels.append(self.label2id[groundtruth_category])
            abstract_id = int(asset["externalId"])
            abstract = SsrnAbstract(abstract_id)
            abstract.from_kili(project_id=self.kili_project_id)
            text = str(abstract)
            texts.append(text)
        if len(labels) == 0 or len(texts) == 0:
            print("There is no data for training. Please check the assets list.")
            return
        dataset_dict = {"label": labels, "text": texts}
        dataset = Dataset.from_dict(dataset_dict)
        dataset = dataset.train_test_split(test_size=0.2)
        tokenized_dataset = dataset.map(self.__preprocess_function, batched=True)

        training_args = TrainingArguments(
            output_dir=self.model_name,
            learning_rate=2e-5,
            per_device_train_batch_size=16,
            per_device_eval_batch_size=16,
            num_train_epochs=3,
            weight_decay=0.01,
            evaluation_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            push_to_hub=True,
        )
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=tokenized_dataset["train"],
            eval_dataset=tokenized_dataset["test"],
            tokenizer=self.tokenizer,
            data_collator=self.data_collator,
            compute_metrics=self.__compute_metrics,
        )
        trainer.train()

    def predict(self):
        """
        Predicts the category of a text.
        """
        classifier = pipeline(
            "text-classification", model=self.model_name, tokenizer=self.tokenizer
        )
        assets = self.kili_client.assets(
            project_id=self.kili_project_id,
            fields=["id", "externalId"],
            status_in=["TODO"],
        )
        for asset in tqdm(assets):
            abstract_id = int(asset["externalId"])
            abstract = SsrnAbstract(abstract_id)
            abstract.from_kili(project_id=self.kili_project_id)
            text = str(abstract)
            try:
                prediction = classifier(text)
            except RuntimeError:
                continue
            predicted_label = {
                "IS_STRATEGY": {"categories": [{"name": prediction[0]["label"]}]}
            }
            self.kili_client.append_labels(
                asset_id_array=[asset["id"]],
                json_response_array=[predicted_label],
                model_name=self.model_name,
                disable_tqdm=True,
                label_type="PREDICTION",
            )
            priority = int(100 * (1 - prediction[0]["score"]))
            self.kili_client.update_properties_in_assets(
                asset_ids=[asset["id"]],
                priorities=[priority],
            )


@click.command()
@click.option("--mode", default="train")
@click.option("--kili-project-id")
def main(mode, kili_project_id):
    """
    Main function.
    """
    ssrn_abstract_classifier = SsrnAbstractClassifier(kili_project_id=kili_project_id)
    if mode == "train":
        ssrn_abstract_classifier.train()
    elif mode == "predict":
        ssrn_abstract_classifier.predict()


if __name__ == "__main__":
    main()
