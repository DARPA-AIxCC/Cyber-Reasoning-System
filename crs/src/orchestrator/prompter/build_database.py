from megavul import load_dataset
from config import DATA_PATH, CHROMA_PATH, COLLECTION_NAME

from embeddings import EmbeddingGenerator

from tqdm import tqdm
import sys

try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    raise ImportError("pysqlite3 module is required to replace sqlite3.")

import chromadb
from utils import logger


if __name__ == "__main__":
    df = load_dataset(DATA_PATH)

    sources = df.func_before
    patches = df.func
    diffs = df.diff_func
    cwes = df.cwe_ids

    unique_cwes = sorted({cwe for sublist in cwes for cwe in sublist})

    onehot_cwe = []
    for cwe_list in cwes:
        row_dict = {cwe: 1 if cwe in cwe_list else 0 for cwe in unique_cwes}
        onehot_cwe.append(row_dict)

    model = EmbeddingGenerator()

    source_embeds = []

    for idx, source in tqdm(enumerate(sources)):
        source_embeds.append(model.get_embeddings(source))
        print(f"Completed iteration {idx} of {len(sources)}.")

    logger.info("Done generating embeddings.")
    client = chromadb.PersistentClient(path="./data_store")
    # client.delete_collection('megavul')

    collection = client.create_collection(
        name="megavul", metadata={"hnsw:space": "cosine"}
    )

    embeds = [list(embed[0]) for embed in source_embeds]

    collection.add(
        documents=sources.to_list(),
        embeddings=embeds,
        ids=[f"program_{i}" for i in range(1, len(sources) + 1)],
        metadatas=[
            {"diff": diffs[i], "patch": patches[i], **onehot_cwe[i]}
            for i in range(len(sources))
        ],
    )
    logger.info(
        f"Built ChromaDB database in {CHROMA_PATH} "
        f"for collection {COLLECTION_NAME}."
    )
