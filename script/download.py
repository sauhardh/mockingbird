import gdown
import os

DATASET_PATH = "data/birds_dataset.xlsx"

FILE_ID = "1_Peid9PPAKI9H44NS9RIK-S-VWpd4y8l"

URL = f"https://drive.google.com/uc?id={FILE_ID}"

# make sure folder exists
os.makedirs(os.path.dirname(DATASET_PATH), exist_ok=True)

if not os.path.exists(DATASET_PATH):
    print("Downloading dataset...")
    gdown.download(URL, DATASET_PATH, quiet=False)
    print("Download complete.")
else:
    print("Dataset already exists.")