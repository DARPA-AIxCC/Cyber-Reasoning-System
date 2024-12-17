
# hermes

This is a library that builds prompts to repair input programs in two stages. First, it asks an LLM to describe the bug in the input program. Second, it fetches similar examples (first filtered by CWE-ID, then sorted by embedding similarity). Finally, it uses the generated description and fetched examples to query an LLM (the same or different, see configuration options below) to perform the repair. Hermes will automatically adjust the number of examples to populate the prompt with, based on the chosen model's prompt limit.

## Installation

This was tested using Python 3.11.0.

Setup is very straightforward:

 1. Make sure you create a new virtual environment (we recommend [`pyenv-virtualenv`](https://github.com/pyenv/pyenv-virtualenv)).
 2. Make sure you have a `data_store` directory. To do this, you can either (a) ask us for it, or (b) make your own using `build_database.py`. If you choose option (b), you will need to download `megavul_lite.json` from the [MegaVul repository](https://github.com/lcyrockton/MegaVul).
 3. Finally, install the requirements using pip:

```bash
pip  install  -r  requirements.txt
```

## Configuration

All configuration can be found in `config.toml` and `config.py`:

- In `config.toml`, the user is expected to store all access tokens (OpenAI, Anthropic, and Google) for LiteLLM to use. In addition:
  - `data_path`: the location of the database to use when looking for similar programs to include as examples in the prompt. We currently use [MegaVul](https://github.com/Icyrockton/MegaVul) to look for programs.
  - `chroma_path`: the location of the [ChromaDB](https://docs.trychroma.com/) vector database to use to look for examples. If using your own, make sure your database contains the same fields as the ones in `build_database.py`.
  - `collection_name`: the name of the collection inside the vector database. Currently we use `megavul`.
- In `config.py`, we have the following options:
  - `LOCAL`: a boolean used to determine whether to generate the embeddings locally or online. If online, we use the [`LiteLLM`](https://docs.litellm.ai/) library. The default option is `text-embedding-3-large` from OpenAI, but [any embedding model from LiteLLM](https://litellm.vercel.app/docs/embedding/supported_embedding) is supported.
  - `CHROMA`: a boolean used to determine whether we will use a local ChromaDB instance to get the examples from, or if a `json` should be used. Specific parameters for this are described in `config.toml` above.
  - `DESCRIPTION_PROMPT`: the system prompt used for the description task.
  - `REPAIR_PROMPT`: the system prompt used for the repair task.
  - `DESCRIPTION_MODELS`: the models to use for the description task. This should be a list, even if it has one element.
  - `REPAIR_MODELS`: the models to use for the repair task. This should be a list, even if it has one element.
  - `NUM_NEIGHBORS`: the number of examples to include in the prompt. This is an *upper limit* on the number of examples, since `hermes` will only add examples if the model's context window allows it.
  - `EMBEDDING_MODEL`: the model to use to generate embeddings. If online, has to be one of `ONLINE_EMBEDDINGS`. If offline (i.e. using `sentence_transformers`), has to be one of `LOCAL_EMBEDDINGS`.
  - `EMBEDDING_DIM`: dimension of embeddings to fetch from an online embedding generator. Option was tested using OpenAI's `text-embedding-3-large`; other providers might not support it.

## Usage

`hermes` is built as a library with an accompanying command-line interface. The CLI is available via `cli.py`, and it can be used as follows:

```bash
python cli.py jenkins.txt java CWE-200 18 output
```

The arguments it expects are:

 1. A text file with the program-to-fix in it (e.g. `jenkins.txt` above).
 2. The language in which the input file is written. Supported options are `c++`, `cpp`, `c`, `java`, and `python`.
 3. The CWE-ID for the program. This is then used to retrieve programs with the same CWE-ID from MegaVul (e.g. `CWE-200`).
 4. The line number at which the bug is localized (e.g. `18`).
 5. The output directory (e.g. `output`).
