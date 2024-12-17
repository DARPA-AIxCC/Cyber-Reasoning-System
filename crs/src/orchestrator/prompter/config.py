try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import pathlib
from log import logger

import os
import json


with open("config.toml", mode="rb") as fp:
    config = tomllib.load(fp)


MODEL_COST_FILE = "model_cost.json"
with open(MODEL_COST_FILE, "r") as file:
    model_cost = json.load(file)

PROXY = False
VALIDATE_KEYS = True

# ============== LLM Access Tokens ============
if "OPENAI_API_KEY" not in os.environ:
    OPENAI_TOKEN = config["openai"]["openai_token"]
    os.environ["OPENAI_API_KEY"] = OPENAI_TOKEN
else:
    OPENAI_TOKEN = os.getenv("OPENAI_API_KEY")


if "ANTHROPIC_API_KEY" not in os.environ:
    ANTHROPIC_TOKEN = config["anthropic"]["anthropic_token"]
    os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_TOKEN
else:
    ANTHROPIC_TOKEN = os.getenv("ANTHROPIC_API_KEY")


if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    GOOGLE_TOKEN = config["google"]["gemini_token"]
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_TOKEN
else:
    GOOGLE_TOKEN = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# ================ LiteLLM Config ==============
if "LITELLM_KEY" not in os.environ:
    LITELLM_KEY = config["litellm"]["litellm_key"]
    os.environ["LITELLM_KEY"] = LITELLM_KEY
else:
    LITELLM_KEY = os.getenv("LITELLM_KEY", None)
LITELLM_KEY = f"Bearer {LITELLM_KEY}"

if "AIXCC_LITELLM_HOSTNAME" not in os.environ:
    LITELLM_HOSTNAME = config["litellm"]["litellm_hostname"]
    os.environ["AIXCC_LITELLM_HOSTNAME"] = LITELLM_HOSTNAME
else:
    LITELLM_HOSTNAME = os.getenv("AIXCC_LITELLM_HOSTNAME", None)

if not PROXY:
    LITELLM_KEY = None
    LITELLM_HOSTNAME = None

# ============== Supported Models via LiteLLM ============
if PROXY:
    OPENAI_MODELS = [
        "oai-gpt-4o",
        "oai-gpt-4",
        "oai-gpt-4-turbo",
        "oai-gpt-3.5-turbo",
        "oai-gpt-3.5-turbo-16k",
    ]

    ANTHROPIC_MODELS = ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
    GOOGLE_MODELS = ["gemini-1.0-pro", "gemini-1.5-pro"]
else:
    OPENAI_MODELS = [
        "gpt-4o-2024-05-13",
        "gpt-4-turbo-2024-04-09",
        "gpt-4-0613",
        "gpt-3.5-turbo-0125",
    ]
    ANTHROPIC_MODELS = [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
    ]
    GOOGLE_MODELS = ["gemini-1.0-pro-001", "gemini-1.5-pro-preview-0409"]

# ============== Parameters ============
LOCAL = False
CHROMA = True

DESCRIPTION_PROMPT = "You are a security expert with a specialty in fixing vulnerable \
code. I will give you a program and its corresponding CWE, and \
I would like you to describe what the issue is."

REPAIR_PROMPT = "You are a security expert with a specialty in \
fixing code vulnerabilities. \
You will be given a few example programs with their fixes as diffs, \
followed by a program to fix and its CWE-ID. I will also give you a \
description of the bug. \
Your output should be the fixed code. \
Make sure the code is between ``` and ```. Do not add the language to \
the first line."

REVIEW_PROMPT = "You are a security expert and your job will be to review a suggested \
patch. I will give you a program that has a security vulnerability, \
its CWE ID, and a suggested patch. Your output will be code only: \
If the patch looks good to you, return the patch itself. If it doesn't, \
return a new patch. No explanation is necessary. \
Your review should be done in steps: first, are there any syntax issues?\
Second, does the proposed patch address the given CWE?"


NUM_NEIGHBORS = 10

# https://huggingface.co/models?library=sentence-transformers
LOCAL_EMBEDDINGS = {
    "minilm1": "multi-qa-MiniLM-L6-cos-v1",
    "minilm2": "sentence-transformers/all-MiniLM-L6-v2",
    "glove300d": "sentence-transformers/average_word_embeddings_glove.6B.300d",
    "robertacode": "flax-sentence-embeddings/st-codesearch-distilroberta-base",
    "codebert": "microsoft/codebert-base",
    "codet5": "Salesforce/codet5-base",
    "hfbert": "huggingface/CodeBERTa-language-id",
    "graphcodebert": "microsoft/graphcodebert-base",
}

OPENAI_EMBEDDINGS = ["text-embedding-3-large", "text-embedding-3-small"]
GOOGLE_EMBEDDINGS = ["vertex_ai/textembedding-gecko@003"]
ONLINE_EMBEDDINGS = OPENAI_EMBEDDINGS + GOOGLE_EMBEDDINGS


# EMBEDDING_MODEL = 'graphcodebert'
EMBEDDING_MODEL = "text-embedding-3-large"
if LOCAL:
    assert EMBEDDING_MODEL in LOCAL_EMBEDDINGS.keys()
else:
    assert EMBEDDING_MODEL in ONLINE_EMBEDDINGS

EMBEDDING_DIM = 3072

if CHROMA:
    CHROMA_PATH = config["data"]["chroma_path"]
    COLLECTION_NAME = config["data"]["collection_name"]
else:
    DATA_PATH = pathlib.Path(config["data"]["data_path"])
    logger.info(f"Set data path to {DATA_PATH}.")
    if not pathlib.Path.is_file(DATA_PATH):
        raise ValueError(f"{DATA_PATH} is not a valid file.")
