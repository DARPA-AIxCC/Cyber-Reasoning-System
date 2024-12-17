try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import pathlib
from hermes.log import logger

import os
import json


config_path = pathlib.Path('./config.toml')
with open(config_path, mode='rb') as fp:
    config = tomllib.load(fp)


model_cost_path = pathlib.Path('./hermes/config/model_cost.json')
with open(model_cost_path, 'r') as file:
    model_cost = json.load(file)

PROXY = True if 'AIXCC_CRS_SCRATCH_SPACE' in os.environ else False
VALIDATE_KEYS = False
WRITE_TEMP = False

# ============== Embedding parameters ============
NUM_NEIGHBORS = 5
EMBEDDING_DIM = 3072

LOCAL = False
CHROMA = True

MAX_WORKERS = 4
VALIDATE_AZURE = True
# =============== LLM Access Tokens =============
if "OPENAI_API_KEY" not in os.environ:
    OPENAI_TOKEN = config['openai']['openai_token']
    os.environ['OPENAI_API_KEY'] = OPENAI_TOKEN
else:
    OPENAI_TOKEN = os.getenv("OPENAI_API_KEY")


if "ANTHROPIC_API_KEY" not in os.environ:
    ANTHROPIC_TOKEN = config['anthropic']['anthropic_token']
    os.environ['ANTHROPIC_API_KEY'] = ANTHROPIC_TOKEN
else:
    ANTHROPIC_TOKEN = os.getenv("ANTHROPIC_API_KEY")


if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    GOOGLE_TOKEN = config['google']['gemini_token']
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_TOKEN
else:
    GOOGLE_TOKEN = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")


if "AZURE_API_KEY" not in os.environ:
    AZURE_API_KEY = config.get('azure', {}).get('azure_key', '')
    os.environ['AZURE_API_KEY'] = AZURE_API_KEY
else:
    AZURE_API_KEY = os.getenv('AZURE_API_KEY')

if "AZURE_API_BASE" not in os.environ:
    AZURE_API_BASE = config.get('azure', {}).get('azure_endpoint', '')
    os.environ['AZURE_API_BASE'] = AZURE_API_BASE
else:
    AZURE_API_BASE = os.getenv('AZURE_API_BASE')

os.environ['AZURE_API_VERSION'] = '2024-02-01'

# ================ LiteLLM Config ==============
if "LITELLM_KEY" not in os.environ:
    LITELLM_KEY = config['litellm']['litellm_key']
    os.environ['LITELLM_KEY'] = LITELLM_KEY
else:
    LITELLM_KEY = os.getenv("LITELLM_KEY", None)
LITELLM_KEY = f"Bearer {LITELLM_KEY}"

if "AIXCC_LITELLM_HOSTNAME" not in os.environ:
    LITELLM_HOSTNAME = config['litellm']['litellm_hostname']
    os.environ['AIXCC_LITELLM_HOSTNAME'] = LITELLM_HOSTNAME
else:
    LITELLM_HOSTNAME = os.getenv("AIXCC_LITELLM_HOSTNAME", None)

if not PROXY:
    LITELLM_KEY = None
    LITELLM_HOSTNAME = None

# ============== Supported Models via LiteLLM ============
if PROXY:
    AZURE_MODELS = [
        'azure-gpt-4o',
        'azure-gpt-3.5-turbo',
    ]
    OPENAI_MODELS = [
        'oai-gpt-4o',
        'oai-gpt-4',
        'oai-gpt-4-turbo',
        'oai-gpt-3.5-turbo',
    ]
    ANTHROPIC_MODELS = [
        'claude-3-opus',
        'claude-3-sonnet',
        'claude-3-haiku',
        'claude-3.5-sonnet'
    ]
    GOOGLE_MODELS = [
        'gemini-1.0-pro',
        'gemini-1.5-pro'
    ]
else:
    AZURE_MODELS = [
        'azure/gpt-4o',
        'azure/gpt-35-turbo',
    ]
    OPENAI_MODELS = [
        'gpt-4o-2024-05-13',
        'gpt-4-0613',
        'gpt-4-turbo-2024-04-09',
        'gpt-3.5-turbo-0125',
    ]
    ANTHROPIC_MODELS = [
        'claude-3-opus-20240229',
        'claude-3-sonnet-20240229',
        'claude-3-haiku-20240307',
        'claude-3-5-sonnet-20240620'
    ]
    GOOGLE_MODELS = [
        'gemini-1.0-pro-001',
        'gemini-1.5-pro-preview-0409'
    ]

# ============== Parameters ============


CWE_DESCRIPTION_PROMPT = (
    "You are a security expert with a specialty in fixing vulnerable \
code. I will give you a program and its corresponding CWE, and \
I would like you to describe what the issue is."
)

BUG_DESCRIPTION_PROMPT = (
    "You are a helpful security expert with a specialty in fixing vulnerable \
code. I want you to help me fix a vulnerable program. I'll give you the \
original program I started with, my understanding of the CWE it has, and then \
I'll show you my attempt at fixing it. I want you to describe what I need \
to change to make my patch work."
)

CWE_REPAIR_PROMPT = (
    "You are a security expert with a specialty in \
fixing code vulnerabilities. \
You will be given a few example programs with their fixes as diffs, \
followed by a program to fix and its CWE-ID. I will also give you a \
description of the bug. \
Your output should be the fixed code. \
Make sure the code is between ``` and ```. Do not add the language to \
the first line."
)

BUG_REPAIR_PROMPT = (
    "You are an expert programmer with a specialty in fixing code. \
I would like your help fixing a program. I'll give you the program \
and a description of the problem, and I would like you to give me a fixed \
version of it. Your output should be only the code. Make sure the code \
is between ``` and ```."
)

REVIEW_PROMPT = (
    "You are a helpful security expert with a specialty in fixing vulnerable \
code. I would like you to review my work in fixing a vulnerability I found \
in a program. I will give you the original program, a description of why \
I think it's vulnerable, its CWE ID, and my attempt at \
fixing it. If my patch looks good to you, output nothing. \
If it doesn't, return a new patch. No explanation is necessary. \
Your output should be code only. Make sure the code is between ``` and ```."
)


# https://huggingface.co/models?library=sentence-transformers
LOCAL_EMBEDDINGS = {
    'minilm1': 'multi-qa-MiniLM-L6-cos-v1',
    'minilm2': 'sentence-transformers/all-MiniLM-L6-v2',
    'glove300d': 'sentence-transformers/average_word_embeddings_glove.6B.300d',
    'robertacode': 'flax-sentence-embeddings/st-codesearch-distilroberta-base',
    'codebert': 'microsoft/codebert-base',
    'codet5': 'Salesforce/codet5-base',
    'hfbert': 'huggingface/CodeBERTa-language-id',
    'graphcodebert': 'microsoft/graphcodebert-base'
}

if PROXY:
    AZURE_EMBEDDINGS = [
        'azure-text-embedding-3-large',
        'azure-text-embedding-3-small'
    ]
    OPENAI_EMBEDDINGS = [
        'oai-text-embedding-3-large',
        'oai-text-embedding-3-small'
    ]
    GOOGLE_EMBEDDINGS = [
        'textembedding-gecko'
    ]
else:
    AZURE_EMBEDDINGS = [
        'azure/text-embedding-3-large',
        'azure/text-embedding-3-small'
    ]
    OPENAI_EMBEDDINGS = [
        'text-embedding-3-large',
        'text-embedding-3-small'
    ]
    GOOGLE_EMBEDDINGS = [
        'textembedding-gecko@003'
    ]
ONLINE_EMBEDDINGS = AZURE_EMBEDDINGS + OPENAI_EMBEDDINGS + GOOGLE_EMBEDDINGS


# EMBEDDING_MODEL = 'graphcodebert'
EMBEDDING_MODEL = OPENAI_EMBEDDINGS[0]
if LOCAL:
    assert EMBEDDING_MODEL in LOCAL_EMBEDDINGS.keys()
else:
    assert EMBEDDING_MODEL in ONLINE_EMBEDDINGS


if CHROMA:
    CHROMA_PATH = config['data']['chroma_path']
    COLLECTION_NAME = config['data']['collection_name']
else:
    DATA_PATH = pathlib.Path(config['data']['data_path'])
    logger.info(f'Set data path to {DATA_PATH}.')
    if not pathlib.Path.is_file(DATA_PATH):
        raise ValueError(f'{DATA_PATH} is not a valid file.')
