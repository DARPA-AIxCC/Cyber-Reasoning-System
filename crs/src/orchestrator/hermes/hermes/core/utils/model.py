from litellm import completion, encode
import litellm

from hermes.config.config import (
    LITELLM_KEY,
    LITELLM_HOSTNAME,
    PROXY,
    model_cost
)
from hermes.log import logger

import concurrent.futures
import time
from tqdm import tqdm

from collections.abc import Iterable


litellm.drop_params = True


class ModelUtils:
    @staticmethod
    def get_proxy_model_id(model_id):
        """Given a model_id, do the following:
        -   If the DARPA Proxy is used, return the LiteLLM-compatible
        model_id.
        -   Otherwise, return the model_id as-is.
        This is useful to keep compatibility with other utils, e.g.
        count_tokens, token_limit, etc... which use LiteLLM IDs.

        Parameters
        ----------
        model_id : [str]

        Returns
        -------
        [str]
        """
        PROXY_ID = {
            'azure-gpt-4o': 'azure/gpt-4o',
            'azure-gpt-3.5-turbo': 'azure/gpt-35-turbo',
            'oai-gpt-4o': 'gpt-4o-2024-05-13',
            'oai-gpt-4': 'gpt-4-0613',
            'oai-gpt-4-turbo': 'gpt-4-turbo-2024-04-09',
            'oai-gpt-3.5-turbo': 'gpt-3.5-turbo-0125',
            'claude-3-opus': 'claude-3-opus-20240229',
            'claude-3-sonnet': 'claude-3-sonnet-20240229',
            'claude-3-haiku': 'claude-3-haiku-20240307',
            'claude-3.5-sonnet': 'claude-3-5-sonnet-20240620',
            'gemini-1.0-pro': 'gemini-1.0-pro-002',
            'gemini-1.5-pro': 'gemini-1.5-pro-preview-0514'
        }
        if not PROXY:
            return model_id
        if model_id not in PROXY_ID.keys():
            logger.warning(f'{model_id} not in supported proxy models')
            return model_id
        return PROXY_ID[model_id]

    @staticmethod
    def azure_to_oai(model_id):
        """Translate Azure model endpoints to OpenAI endpoints.

        Parameters
        ----------
        model_id : [str]

        Returns
        -------
        [str]
            Translated model_id.
        """
        translation = {
            'azure/gpt-4o': (
                'oai-gpt-4o' if PROXY else 'gpt-4o-2024-05-13'
            ),
            'auzre/gpt-35-turbo': (
                'oai-gpt-3.5-turbo' if PROXY else 'gpt-3.5-turbo-0125'
            ),
            'azure-gpt-4o': (
                'oai-gpt-4o' if PROXY else 'gpt-4o-2024-05-13'
            ),
            'auzre-gpt-35-turbo': (
                'oai-gpt-3.5-turbo' if PROXY else 'gpt-3.5-turbo-0125'
            )
        }
        if model_id not in translation.keys():
            logger.warning(f'{model_id} is not a supported Azure model.')
            return model_id
        return translation[model_id]


    @staticmethod
    def _call_model(model_id, user_prompt, system_prompt):
        """Helper function that will call a LiteLLM.completion() given
        a model_id, user prompt, and system prompt.
        Automatically adjusts parameters based on whether or not the proxy
        is being used.

        Parameters
        ----------
        model_id : [str]
            model_id
        user_prompt : [str]
            user prompt, e.g. "Hello, how are you?"
        system_prompt : [str]
            system prompt, e.g. "Answer my questions" or "Translate to French"

        Returns
        -------
        [str]
            Raw string content of the response from the model
        """
        logger.info(f'Calling {model_id}.')
        response = completion(
                    model=model_id,
                    custom_llm_provider='openai' if PROXY else '',
                    extra_headers={
                        "Authorization": LITELLM_KEY
                    } if LITELLM_KEY else {},
                    base_url=LITELLM_HOSTNAME,
                    messages=[
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    num_retries=1
                )
        answer = response.choices[0].message['content']
        if answer:
            logger.info(f'Received response from {model_id}.')
        return answer

    @staticmethod
    def retry_call(model_id, user_prompt, system_prompt, wait_time=65):
        """Retry call to model after waiting [wait_time] seconds.

        Parameters
        ----------
        model_id : [str]
            model_id
        user_prompt : [str]
            user prompt, e.g. "Hello, how are you?"
        system_prompt : [str]
            system prompt, e.g. "Answer my questions" or "Translate to French"

        wait_time : int, optional
            Time to wait, in seconds. By default 65

        Returns
        -------
        [str]
            -   If an answer is received after retrying once, return it.
            -   Otherwise, return an empty string.
        """
        logger.warning(
            f'Rate limit error from {model_id}. '
            f'Retrying after {wait_time} seconds.')
        for _ in tqdm(range(wait_time), desc="Waiting", unit="s"):
            time.sleep(1)
        try:
            answer = ModelUtils._call_model(
                model_id=model_id,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )
        except Exception as e:
            logger.warning(f'Retrying {model_id} resulted in {e}.')
            answer = ''
        return answer
    @staticmethod
    def call_model(model_id, user_prompt, system_prompt):
        """Function to call a model. This is just a wrapper around
        _call_model().
        If _call_model() succeeds, the response is returned.
        Otherwise:
        -   If _call_model raises an APIConnectionError, this will attempt
        to get the non-Azure model_id and do the call again.
        If a RateLimitError is raised, it will wait 65s and then try again.
        -   If _call_model raises a RateLimitError, this will wait 65s before
        trying again.
        -   If _call_model raises another exception, this will add a warning
        to the log and return an empty string.

        Parameters
        ----------
        model_id : [str]
            model_id
        user_prompt : [str]
            user prompt, e.g. "Hello, how are you?"
        system_prompt : [str]
            system prompt, e.g. "Answer my questions" or "Translate to French"


        Returns
        -------
        [str]
            Raw string content of the response from the model
        """
        start_time = time.monotonic()
        logger.info(f'Attempting to call {model_id}.')
        try:
            answer = ModelUtils._call_model(
                model_id=model_id,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )
        except litellm.RateLimitError:
            logger.warning(f'{model_id} raise a RateLimitError. Retrying.')
            answer = ModelUtils.retry_call(
                model_id=model_id,
                user_prompt=user_prompt,
                system_prompt=system_prompt
            )
        except Exception as e:
            logger.warning(f'Calling {model_id} resulted in {type(e).__name__}.')
            answer = ''
        end_time = time.monotonic()
        logger.info(f'Calling {model_id} took {end_time - start_time:.2f}s.')
        return answer

    @staticmethod
    def batch_call(models, user_prompt, system_prompt):
        """Call multiple models with the same user and system prompts in
        parallel.

        Parameters
        ----------
        models : List[str]
            model_id's to call in parallel
        user_prompt : [str]
            user prompt, e.g. "Hello, how are you?"
        system_prompt : [str]
            system prompt, e.g. "Answer my questions" or "Translate to French"
        """
        start_time = time.monotonic()
        def batch_helper(model_id):
            output = ModelUtils.call_model(model_id, user_prompt, system_prompt)
            return (model_id, output)

        if not isinstance(models, Iterable):
            raise TypeError(
                f'Excepted models to be a iterable. Got {type(models)}.'
            )
        if len(models) <= 0:
            raise ValueError('models must have at least one element.')

        if len(models) == 1:
            return {
                models[0]:
                    ModelUtils.call_model(
                        models[0],
                        user_prompt,
                        system_prompt
                    )
                }

        logger.info(f'Attempting to call {models} in a batch.')
        responses = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(models)) as executor:
            futures = [
                executor.submit(
                    batch_helper,
                    model_id
                ) for model_id in models
            ]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result is not None:
                    model_id, output = result
                    responses[model_id] = output
        end_time = time.monotonic()
        logger.info(
            f'Batch call for {models} took {end_time - start_time: .2f}s.'
        )
        return responses

    @staticmethod
    def check_valid_key(model_id):
        """Helper function to check if the registered API keys are valid for
        the given model_id.

        Parameters
        ----------
        model_id : [str]
            id of the model to check

        Returns
        -------
        [bool]
            -   True if there's a valid registered API key to use with
            the given model_id.
            -   False otherwise.
        """
        user_prompt = "Test."
        system_prompt = ""

        start_time = time.monotonic()
        logger.info(f'Attempting to validate keys for {model_id}.')
        try:
            ModelUtils._call_model(
                model_id=model_id,
                user_prompt=user_prompt,
                system_prompt=system_prompt)
            end_time = time.monotonic()
            logger.info(
                f'Validating keys for {model_id} succeeded '
                f'after {end_time - start_time: .2f}s.'
            )
            return True
        except Exception as e:
            end_time = time.monotonic()
            logger.warning(
                f'Validating key for {model_id} failed '
                f'after {end_time - start_time: .2f}s.'
                f'Received {type(e).__name__}.'
            )
            return False

    @staticmethod
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
            model_id = ModelUtils.get_proxy_model_id(model_id=model_id)
        return len(encode(model=model_id, text=text))

    @staticmethod
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
            model_id = ModelUtils.get_proxy_model_id(model_id=model_id)
        max_input_tokens = model_cost[model_id]['max_input_tokens']
        max_output_tokens = model_cost[model_id]['max_output_tokens']
        return (max_input_tokens - max_output_tokens)

    @staticmethod
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
            models = [
                model_id
                for model_id in models
            ]
            print(models)
        filtered_models = [
            model_id for model_id in models
            if ModelUtils.token_limit(
                model_id=model_id
                ) >= ModelUtils.count_tokens(model_id=model_id, text=text)
        ]
        if filtered_models:
            logger.info(
                f'Retaining {len(filtered_models)} from {len(models)} models.'
            )
        else:
            logger.warning(
                'All the provided models cannot accept the input text.'
            )
        return filtered_models
