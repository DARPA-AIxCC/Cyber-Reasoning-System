import numpy as np
import pandas as pd

from hermes.core.embeddings import EmbeddingGenerator
from hermes.core.distance import DistanceMetric
from hermes.log import logger
from hermes.config.config import EMBEDDING_DIM


class LocalSearch():
    def __init__(self, metric):
        assert isinstance(metric, DistanceMetric)
        self.model = EmbeddingGenerator()
        self.metric = metric

    def get_candidates(cwe_id, df):
        """Return all rows with cwe_id.

        Parameters
        ----------
        cwe_id : [str]
            CWE-ID to use to filter the dataframe.
        df : [pandas.DataFrame]
            A dataframe within which to search for candidate programs.
            Must include 'cwe_ids' column.

        Returns
        -------
        [pandas.DataFrame]
            DataFrame of candidates whose CWE-ID matches the input cwe_id.
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Expected pd.DataFrame. Got {type(df)} instead.")
        if "cwe_ids" not in df.columns:
            raise KeyError("Did not find cwe_ids column in df.")
        logger.info(f'Getting candidates with CWE-ID: {cwe_id}.')
        return df[df["cwe_ids"].apply(lambda x: cwe_id in x)]


    def prepare_candidates(candidates):
        logger.info(f'Preparing {len(candidates)} candidates.')
        model = EmbeddingGenerator()
        before = []
        after = []
        diff = []
        for _, candidate in candidates.iterrows():
            before.append(candidate.func_before)
            after.append(candidate.func)
            diff.append(candidate.diff_func)

        # Sanity check: make sure there are no NaNs or empty values
        assert len(candidates) == len(before)
        assert len(before) == len(after)
        assert len(after) == len(diff)
        before = before
        after = after
        diff = diff
        embeddings = model.get_embeddings(before)
        return before, after, embeddings, diff


    def sort_candidates(source, embeddings, diffs, metric):
        """Sort candidate programs by distance to source program.

        Parameters
        ----------
        source : [np.array]
            Embedding of the source (input) program
        embeddings : [List[np.array]]
            List of the embeddings of all the candidate programs
        diffs : [List[str]]
            List of candidate diffs
        metric : [DistanceMetric]
            Metric to use to compute distance.
            e.g. L2 or Cosine
            Must implement .compute().

        Returns
        -------
        [tuple([List[np.array]], [List[np.float]])]
            Two objects:
            1.  The sorted embeddings
            2.  A list of distances: elem[i] is the distance between the i-th
                program and the source.
        """
        logger.info(f'Sorting {len(embeddings)} by {metric}.')
        # Get distance between each candidate and the source program
        distances = [
            metric.compute(source, candidate) for candidate in embeddings]
        # Sort the distances
        indices = np.argsort(distances)
        # Get the diffs for each sorted candidate
        neighbors = [diffs[idx] for idx in indices]

        return neighbors, distances


    def search(self, source, cwe_id, df, number=None):
        """Search for similar programs to sourcein dataframe,
        filtering by CWE-ID first.

        Parameters
        ----------
        source : [str]
            Input source program.
        cwe_id : [str]
            CWE-ID of input program.
        df : [pandas.DataFrame]
            DataFrame in which to search for candidates.
        number : [int], optional
            Number of similar programs to return.
            If no number is given, all similar programs are returned.

        Returns
        -------
        [List[str]]
            List of diffs of similar programs.
        """
        candidates = self.get_candidates(cwe_id=cwe_id, df=df)
        _, _, embeddings, diffs = self.prepare_candidates(candidates)

        source_embed = self.model.get_embeddings([source])

        metric = self.metric()
        neighbors, _ = self.sort_candidates(source_embed, embeddings, diffs, metric)

        return neighbors[:number]

class ChromaSearch():
    def __init__(self, collection):
        self.model = EmbeddingGenerator()
        self.collection = collection

    def search(self, source, cwe_id, count):
        if source:
            source_embeds = self.model.get_embeddings(source)
            if source_embeds is None:
                logger.warning('Could not generate embeddings. Using zeros.')
                source_embeds = [0] * EMBEDDING_DIM
            query = self.collection.query(
                query_embeddings=source_embeds,
                n_results=count,
                where={f'{cwe_id}': {'$eq': 1}}
            )
            return [neighbor['diff'] for neighbor in query['metadatas'][0]]
        else:
            logger.warning(
                'Empty source given to ChromaSearch.search(). Skipping.'
            )
            return None
