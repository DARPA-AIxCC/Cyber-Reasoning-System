import json
from pathlib import Path
import pandas as pd

from hermes.log import logger


def load_dataset(data_path):
    with Path(data_path).open(mode='r') as f:
        df = pd.DataFrame.from_records(json.load(f))
        df = df[df['is_vul']].reset_index(drop=True)
        # To fit within the GPT-4 context window
        df = df[df['func'].apply(len) <= 20000].reset_index(drop=True)
    logger.info(f'Successfully loaded MegaVul with shape {df.shape}.')
    return df



def extract_sample(df, index):
    sample = df.loc[index]
    return {
        'before': sample.func_before,
        'after': sample.func,
        'diff': sample.diff_func
    }
