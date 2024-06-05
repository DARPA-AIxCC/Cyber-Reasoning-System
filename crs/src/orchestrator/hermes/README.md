
# hermes

This is a library that builds prompts to repair input programs in two stages. First, it asks an LLM to describe the bug in the input program. Second, it fetches similar examples (first filtered by CWE-ID, then sorted by embedding similarity). Finally, it uses the generated description and fetched examples to query an LLM (the same or different, see configuration options below) to perform the repair. `hermes` will automatically adjust the number of examples to populate the prompt with, based on the chosen model's prompt limit. As a last step, `hermes` will ask
a model to review the generated patch and suggest edits to it.
The reviewed patch, in addition to the non-reviewed patch, will both be saved as diffs.

## Installation

This was tested using Python 3.11.0.

Setup is very straightforward:

 1. Make sure you create a new virtual environment (we recommend [`pyenv-virtualenv`](https://github.com/pyenv/pyenv-virtualenv)).
 2. Make sure you have a `data_store` directory. To do this, you can either (a) ask us for it, or (b) make your own using `hermes/helpers/build_database.py`. If you choose option (b), you will need to download `megavul_lite.json` from the [MegaVul repository](https://github.com/lcyrockton/MegaVul). This is the directory that will contain the ChromaDB database to use when fetching examples for the repair step.
 3. Finally, install the requirements using pip:

```bash
pip  install  -r  requirements.txt
```

## Configuration

All configuration can be found in `config.toml` and `hermes/config/config.py`:

- In `config.toml`, the user is expected to store all access tokens (OpenAI, Anthropic, and Google) for LiteLLM to use.
For the Google token, the library expects an [Application Token](https://cloud.google.com/docs/authentication/token-types#access) as a JSON file.
In addition:
  - `data_path`: the location of the database to use when looking for similar programs to include as examples in the prompt. We currently use [MegaVul](https://github.com/Icyrockton/MegaVul) to look for programs.
  - `chroma_path`: the location of the [ChromaDB](https://docs.trychroma.com/) vector database to use to look for examples. If using your own, make sure your database contains the same fields as the ones in `build_database.py`.
  - `collection_name`: the name of the collection inside the vector database. Currently we use `megavul`.
  - `litellm_key`: the key to use if you choose to use the LiteLLM Proxy. This should not include `Bearer` as it will be automatically prepended.
  - `litellm_hostnam`: the hostname you want to use with the LiteLLM Proxy.
- In `config.py`, we have the following options:
  - `PROXY`: a boolean used to determine whether or not to use the LiteLLM Proxy.
  - `VALIDATE_KEYS`: a boolean used to determine whether or not to validate
  the extracted keys from `config.toml`. If enabled, this will make sure that
  only the models whose access keys are valid are added to `SUPPORTED_MODELS`.
  - `NUM_NEIGHBORS`: the number of examples to include in the prompt. This is an *upper limit* on the number of examples, since `hermes` will only add examples if the model's context window allows it.
  - `EMBEDDING_DIM`: the size of the embedding vector to get from the embedding model used. This is only used when using online embedding generation.
  - `LOCAL`: a boolean used to determine whether to generate the embeddings locally or online. If online, we use the [`LiteLLM`](https://docs.litellm.ai/) library. The default option is `text-embedding-3-large` from OpenAI, but [any embedding model from LiteLLM](https://litellm.vercel.app/docs/embedding/supported_embedding) is supported.
  - `CHROMA`: a boolean used to determine whether we will use a local ChromaDB instance to get the examples from, or if a `json` should be used. Specific parameters for this are described in `config.toml` above.
  - `OPENAI_MODELS`, `ANTHROPIC_MODELS`, and `GOOGLE_MODELS`: a list of models that `hermes` supports via `LiteLLM` from each provider. The IDs are set automatically based on whether or not a proxy is used. If using the proxy, the values used are the ones provided by DARPA for AIxCC.
  - `DESCRIPTION_PROMPT`: the system prompt used for the description task.
  - `REPAIR_PROMPT`: the system prompt used for the repair task.
  - `REVIEW_PROMPT`: the system prompt used for the revision task.
  - `EMBEDDING_MODEL`: the model to use to generate embeddings. If online, has to be one of `ONLINE_EMBEDDINGS`. If offline (i.e. using `sentence_transformers`), has to be one of `LOCAL_EMBEDDINGS`.
  - `EMBEDDING_DIM`: dimension of embeddings to fetch from an online embedding generator. Option was tested using OpenAI's `text-embedding-3-large`; other providers might not support it.
- To specify which models to use for which task (Describe, Repair, Review), you can modify the respective functions in `hermes/utils.py`.

## Usage

`hermes` is built as a library with an accompanying command-line interface. Currently, it can be used in two ways:

### Vulnerability Repair Pipeline

The vulnerability repair pipeline is essentially: (i) describe how a function instantiates some CWE-ID, (ii) repair using some fetched examples, and (iii) review the generated patch.

```bash
python multi_location.py bug_info.json
```

Here's an example of what `bug_info.json` could have inside it:

```json
{
    "localization": [
      {
        "source_path": "tif_jpeg.c",
        "line_number": 1634
      },
      {
        "source_path": "tif_jpeg.c",
        "line_number": 1626
      },
      {
        "source_path": "tif_jpeg.c",
        "line_number": 1400
      },
      {
        "source_path": "tif_jpeg.c",
        "line_number": 1401
      }
    ],
    "stack_trace": [
      {
        "source_file": "tif_ojpeg.c",
        "line": 816
      },
      {
        "source_file": "tif_ojpeg.c",
        "line": 791
      }
    ],
    "language": "c",
    "cwe_id": "CWE-20",
    "output_dir": "output"
}
```

Each element inside `localization` contains a file name and a line number
inside the file. Currently, `hermes` will only consider the first 5 *unique* functions
that are pointed to by the elements inside localization. In the example above, the first two elements refer to the same function, and so will be processed once only. The expected keys are:

 1. The language in which the input file is written. Supported options are `c++`, `cpp`, `c`, `java`, and `python`.
 2. The CWE-ID for the program. This is then used to retrieve programs with the same CWE-ID from MegaVul (e.g. `CWE-200`).
 3. The line number at which the bug is localized (e.g. `18`).
 4. The output directory (e.g. `output`).
 5. `stack_trace`: this should be a list of records that have the keys `source_file` and `line`. This is optional, i.e. `hermes` will not complain if this isn't passed.

### Patch Repair Pipeline

The patch repair pipeline uses the validation results to attempt to repair the patches instead of the vulnerable function directly. It works by informing the model of the original vulnerability (with its description), asking it to describe why the patch fails, and then using this description to repair the patch.

```bash
python feedback.py patch_info.json
```

An example `patch_info.json` looks like:

```json
{
    "cwe_id": "CWE-20",
    "language": "c",
    "base_dir": "",
    "output_dir": "output",
    "patches": [
        {
            "source_path": "tif_jpeg.c",
            "line_number": 1575,
            "patch_file": "Diff file",
            "patch_content": [
                "Diff content as a list of lines"
            ],
        "describer_id": "",
        "description": "Some discription",
        "fixer_id": "",
        "reviewer_id": "",
        "patch_type": "One of [invalid, incorrect, failure-fixing]"
        }
    ]
}
```

The patch repair pipeline can be used in two ways: if a description is given, it will be used directly. If it isn't, then a description of the original vulnerable function and the CWE-ID will be generated (internally, this is referred to as a pre-description step). Then the pipeline continues as described above.

If a description is not given, the `source_path` and `line_number` arguments are inferred from the contents of the `diff` file (specified in `patch_file`). The describer, fixer, and reviewer IDs are also all optional: they are used for logging purposes, and not passing them should not affect functionality.

### Testing

`hermes` also now supports a `-t` or `--test` flag for both of the above pipelines. When used, this would run each individual pipeline with only one model for each step. This is useful to reduce time when testing out new implementation. An example invocation would look like:

```bash
python feedback.py patch_info.json --test
```

Currently, this is set to use `Claude-3-Haiku` for all steps. This can easily be changed from within `hermes/core/config/pipelines.py`.
