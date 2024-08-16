<div align="center">
  <img src="static/images/pwb-toolbox.jpeg" height=200 alt=""/>
  <h1>Toolbox</h1>
</div>

The `pwb-toolbox` package is designed to provide tools and resources for systematic trading strategies. It includes datasets and strategy ideas to assist in developing and backtesting trading algorithms. For detailed instructions on how to use this package effectively, please refer to the associated Substack publication by visiting: https://edarchimbaud.substack.com/.


## Installation

To install the pwb-toolbox package, follow these steps:

```bash
# Install python and its dependencies
sudo apt install python3 python3-pip python3-venv
# Clone the repository or download the package from the official source
git clone https://github.com/edarchimbaud/pwb-toolbox.git
# Navigate to the package directory
cd pwb-toolbox/
# Create a virtual environment
python3 -m venv ~/myenv
# Activate it
source ~/myenv/bin/activate
# Install the required dependencies by running
pip install -r requirements.txt
```

To login to Huggingface Hub with Access Token

```bash
huggingface-cli login
```

## Usage

The `pwb-toolbox` package offers a range of functionalities for systematic trading analysis. Here are some examples of how to utilize the package:

- Crawling Datasets:

```python
HF_USERNAME= PYTHONPATH=$PYTHONPATH:. TWILIO_ACCOUNT_SID= TWILIO_AUTH_TOKEN= TWILIO_FROM= TWILIO_TO= python pwb_toolbox/datasets \
  --username [YOUR_HUGGINGFACE_USERNAME]
```

- Crawling Strategy Ideas:

```python
# Download SSRN paper abtract to a Kili project of id YOUR_KILI_PROJECT_ID
PYTHONPATH=$PYTHONPATH:. python pwb_toolbox/strategy_ideas \
  --mode abstract \
  --jel-code G14 \
  --from-page 1 \
  --kili-project-id [YOUR_KILI_PROJECT_ID]

# Use the abtracts labeled in YOUR_SOURCE_KILI_PROJECT_ID to download SSRN paper PDF
# into another Kili project YOUR_TARGET_KILI_PROJECT_ID
PYTHONPATH=$PYTHONPATH:. python pwb_toolbox/strategy_ideas \
  --mode paper \
  --src-kili-project-id [YOUR_SOURCE_KILI_PROJECT_ID] \
  --tgt-kili-project-id [YOUR_TARGET_KILI_PROJECT_ID]

# Transform the annotations of YOUR_KILI_PROJECT_ID into markdown strategy ID cards
PYTHONPATH=$PYTHONPATH:. python pwb_toolbox/strategy_ideas \
  --mode summary \
  --kili-project-id [YOUR_KILI_PROJECT_ID] \
  --tgt-folder [YOUR_TARGET_FOLDER]
```

## Contributing

Contributions to the `pwb-toolbox` package are welcome! If you have any improvements, new datasets, or strategy ideas to share, please follow these guidelines:

1. Fork the repository and create a new branch for your feature.
2. Make your changes and ensure they adhere to the package's coding style.
3. Write tests to validate the functionality or provide sample usage examples.
4. Submit a pull request, clearly explaining the purpose and benefits of your contribution.

Please note that all contributions are subject to review and approval by the maintainers.

## License

The `pwb-toolbox` package is released under the MIT license. See the LICENSE file for more details.

## Contact

For any questions, issues, or suggestions regarding the `pwb-toolbox` package, please contact the maintainers or create an issue on the repository. We appreciate your feedback and involvement in improving the package.

Happy trading!