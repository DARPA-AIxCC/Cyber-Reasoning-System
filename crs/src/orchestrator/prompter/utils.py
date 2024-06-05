from litellm import completion, encode
import litellm

from pathlib import Path

from config import LITELLM_KEY, LITELLM_HOSTNAME, PROXY, model_cost

from config import OPENAI_MODELS, ANTHROPIC_MODELS, GOOGLE_MODELS
from config import VALIDATE_KEYS


from log import logger

import concurrent.futures


litellm.drop_params = True


def get_proxy_model_id(model_id):
    PROXY_ID = {
        "oai-gpt-4o": "gpt-4o-2024-05-13",
        "oai-gpt-4": "gpt-4-0613",
        "oai-gpt-4-turbo": "gpt-4-turbo-2024-04-09",
        "oai-gpt-3.5-turbo": "gpt-3.5-turbo-0125",
        "oai-gpt-3.5-turbo-16k": "gpt-3.5-16k",
        "claude-3-opus": "claude-3-opus-20240229",
        "claude-3-sonnet": "claude-3-sonnet-20240229",
        "claude-3-haiku": "claude-3-haiku-20240307",
        "gemini-1.0-pro": "gemini-1.0-pro-002",
        "gemini-1.5-pro": "gemini-1.5-pro-preview-0514",
    }
    if not PROXY:
        return model_id
    if model_id not in PROXY_ID.keys():
        logger.warn(f"{model_id} not in supported proxy models")
        return model_id
    return PROXY_ID[model_id]


def call_model(model_id, user_prompt, system_prompt):
    logger.info(f"Calling {model_id}.")
    response = completion(
        model=model_id,
        custom_llm_provider="openai" if PROXY else "",
        extra_headers={"Authorization": LITELLM_KEY} if LITELLM_KEY else {},
        base_url=LITELLM_HOSTNAME,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    answer = response.choices[0].message["content"]
    logger.info(f"Received response from {model_id}.")
    return answer


def batch_call(models, user_prompt, system_prompt):
    def batch_helper(model_id):
        output = call_model(model_id, user_prompt, system_prompt)
        return (model_id, output)

    logger.info(f"Calling {models} in a batch.")

    responses = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(models)) as executor:
        futures = [executor.submit(batch_helper, model_id) for model_id in models]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                model_id, output = result
                responses[model_id] = output
    return responses


def check_valid_key(model_id):
    user_prompt = "Test."
    system_prompt = ""

    try:
        call_model(
            model_id=model_id, user_prompt=user_prompt, system_prompt=system_prompt
        )
        return True
    except Exception as e:
        logger.warn(f"Validating key for {model_id} resulted in {e}.")
        return False


def get_supported_models():
    openai_models = OPENAI_MODELS
    anthropic_models = ANTHROPIC_MODELS
    google_models = GOOGLE_MODELS

    if VALIDATE_KEYS:
        valid_openai = []
        for openai_model in openai_models:
            if not check_valid_key(model_id=openai_model):
                logger.warn(f"OpenAI key is not valid for {openai_model}.")
            else:
                logger.info(f"OpenAI key is valid for {openai_model}.")
                valid_openai.append(openai_model)
        openai_models = valid_openai

        valid_anthropic = []
        for anthropic_model in anthropic_models:
            if not check_valid_key(model_id=anthropic_model):
                logger.warn(f"Anthropic key is not valid for {anthropic_model}.")
            else:
                logger.info(f"Anthropic key is valid for {anthropic_model}.")
                valid_anthropic.append(anthropic_model)
        anthropic_models = valid_anthropic

        valid_google = []
        for google_model in google_models:
            if not check_valid_key(model_id=google_model):
                logger.warn(f"Google key is not valid for {google_model}.")
            else:
                logger.info(f"Google key is valid for {google_model}.")
                valid_google.append(google_model)
        google_models = valid_google

    return {
        "openai": openai_models,
        "anthropic": anthropic_models,
        "google": google_models,
    }


def get_description_models():
    supported_models = get_supported_models()
    description_models = [
        supported_models["openai"][0],
        # supported_models['anthropic'][0],
        # supported_models['google'][0]
    ]
    for model in description_models:
        logger.info(f"Added {model} to chosen description models.")
    return description_models


def get_repair_models():
    supported_models = get_supported_models()
    repair_models = [
        supported_models["openai"][0],
        # supported_models['anthropic'][0],
        # supported_models['google'][0]
    ]
    for model in repair_models:
        logger.info(f"Added {model} to chosen repair models.")
    return repair_models


def get_review_models():
    supported_models = get_supported_models()
    review_models = [
        supported_models["openai"][0],
        # supported_models['anthropic'][0],
        # supported_models['google'][0]
    ]
    for model in review_models:
        logger.info(f"Added {model} to chosen review models.")
    return review_models


def count_tokens(model_id, text):
    """Count the number of tokens in an input string.
    We use LiteLLM's encode() function for this, which will try
    to look for each model's tokenizer to get the tokens.
    If a certain model_id is not supported, it will use OpenAI's tiktoken.

    Parameters
    ----------
    model_id : [str]
        ID of the model used

    text : [str]
        Input string to tokenize and count tokens

    Returns
    -------
    [int]
        Number of tokens in the input_string based on chosen encoding.
    """
    if PROXY:
        model_id = get_proxy_model_id(model_id=model_id)
    return len(encode(model=model_id, text=text))


def token_limit(model_id):
    """Return the maximum number of tokens that the model can take as input.
    Because we access the models via LiteLLM, 'max_input_tokens' includes
    *both* input and output tokens.
    This is why we get the difference between the maximum input tokens and
    the maximum output tokens to get the maximum number of tokens allowed
    in the prompt.

    Parameters
    ----------
    model_id : [str]
        ID of the model used

    Returns
    -------
    [int]
        Maximum number of tokens that can go into the prompt.
    """
    if PROXY:
        model_id = get_proxy_model_id(model_id=model_id)
    max_input_tokens = model_cost[model_id]["max_input_tokens"]
    max_output_tokens = model_cost[model_id]["max_output_tokens"]
    return max_input_tokens - max_output_tokens


def filter_models(models, text):
    """Filter input models to keep only the ones whose input window
    is large enough to accept input text.
    This runs count_tokens() to get the length of [text] in order to check
    if the model can accept it or not.

    Parameters
    ----------
    models : [List[str]]
        A list of model_id's to consider.
    text : [str]
        Input text.

    Returns
    -------
    [List[str]]
        List of model_id's that can accept the input.
    """
    if PROXY:
        models = [model_id for model_id in models]
        print(models)
    filtered_models = [
        model_id
        for model_id in models
        if token_limit(model_id=model_id) >= count_tokens(model_id=model_id, text=text)
    ]
    if filtered_models:
        logger.info(f"Retaining {len(filtered_models)} from {len(models)}.")
    else:
        logger.warn("All the provided models cannot accept the input text.")
    return filtered_models


def setup_directories(output_dir):
    """Setup directories required to store outputs, prompts, and processed
    patches.

    Parameters
    ----------
    output_dir : [pathlib.Path]
        Base directory to store everything in.

    Returns
    -------
    [dict[[str]: [pathlib.Path]]]
        A dict whose keys are strings and values are pathlib.Path objects
        that represent the directories.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source_dir = Path(output_dir) / "source"
    source_dir.mkdir(parents=True, exist_ok=True)

    prompt_dir = Path(output_dir) / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)

    description_prompt_dir = Path(prompt_dir) / "description"
    description_prompt_dir.mkdir(parents=True, exist_ok=True)

    repair_prompt_dir = Path(prompt_dir) / "repair"
    repair_prompt_dir.mkdir(parents=True, exist_ok=True)

    review_prompt_dir = Path(prompt_dir) / "repair"
    review_prompt_dir.mkdir(parents=True, exist_ok=True)

    description_dir = Path(output_dir) / "description"
    description_dir.mkdir(parents=True, exist_ok=True)

    patch_dir = Path(output_dir, "patches")
    patch_dir.mkdir(parents=True, exist_ok=True)

    raw_patch_dir = Path(output_dir, "raw_patches")
    raw_patch_dir.mkdir(parents=True, exist_ok=True)

    review_dir = Path(output_dir, "review")
    review_dir.mkdir(parents=True, exist_ok=True)

    return {
        "output_dir": output_dir,
        "source_dir": source_dir,
        "prompt_dir": prompt_dir,
        "description_prompt_dir": description_prompt_dir,
        "repair_prompt_dir": repair_prompt_dir,
        "review_prompt_dir": review_prompt_dir,
        "description_dir": description_dir,
        "patch_dir": patch_dir,
        "raw_patch_dir": raw_patch_dir,
        "review_dir": review_dir,
    }


def write_file(text: str, path: Path):
    if not isinstance(text, str):
        logger.warn(f"Attempting to write {type(text)}. Casting to string.")
    try:
        with path.open("w") as file:
            file.write(str(text))
        logger.info(f"Successfully wrote {path}.")
    except Exception as e:
        logger.error(f"An error occurred while writing the file: {e}")
