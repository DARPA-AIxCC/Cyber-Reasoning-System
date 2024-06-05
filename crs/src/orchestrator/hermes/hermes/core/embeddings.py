from hermes.config.config import (
    EMBEDDING_MODEL, EMBEDDING_DIM, LOCAL, LOCAL_EMBEDDINGS
)
from hermes.config.config import LITELLM_KEY, LITELLM_HOSTNAME, PROXY

from hermes.log import logger

import numpy as np
from sentence_transformers import SentenceTransformer
from litellm import embedding
import litellm

from openai import OpenAI



litellm.drop_params = True


class EmbeddingGenerator():
    def __init__(self):
        self.model_name = EMBEDDING_MODEL

        self.local = LOCAL
        logger.info(f'Initialized {self.model_name} to generate embeddings.')

    def __repr__(self):
        return f"EmbeddingGenerator({self.model_name}: "\
               f"{self.models[self.model_name]})"

    def get_embeddings(self, sentences):
        if self.local:
            return self.local_embeddings(sentences=sentences)
        else:
            return self.online_embeddings(sentences=sentences)

    def online_embeddings(self, sentences):
        """Generate embeddings online, using LiteLLM.

        Parameters
        ----------
        sentences : [List[str]]
            Sentences for which to generate embeddings.

        Returns
        -------
            [List[np.array]]
            List of embedding vectors.
        """
        logger.info(f'Calling {EMBEDDING_MODEL} to get embeddings.')
        try:
            if PROXY:
                client = OpenAI(
                    api_key=LITELLM_KEY,
                    base_url=LITELLM_HOSTNAME
                )
                output = client.embeddings.create(
                    input=sentences,
                    model=EMBEDDING_MODEL).data[0].embedding
                logger.info('Successfully got embeddings from proxy.')
            else:
                response = embedding(
                    model=EMBEDDING_MODEL,
                    input=sentences,
                    dimensions=EMBEDDING_DIM
                )
                output = np.array(
                    [
                        np.array(elem['embedding']) for elem in response.data
                    ]
                )
                logger.info('Successfully got embeddings from SDK.')
            return output
        except Exception as e:
            logger.warning(f'Embedding generation raised {e}.')
            return None
    def local_embeddings(self, sentences):
        """Generate embeddings locally.
        Uses GPU if available, CPU otherwise.

        Parameters
        ----------
        sentences : [List[str]]
            Sentences for which to generate embeddings.

        Returns
        -------
            [List[np.array]]
            List of embedding vectors.
        """
        model = SentenceTransformer(LOCAL_EMBEDDINGS[self.model_name])
        logger.info(f"Generating {len(sentences)} "
                    "embeddings locally.")
        return model.encode(sentences, show_progress_bar=True)