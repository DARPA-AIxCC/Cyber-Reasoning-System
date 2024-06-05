import sys

try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    raise ImportError("pysqlite3 module is required to replace sqlite3.")

import chromadb
from chromadb.config import Settings

from utils import batch_call, setup_directories, filter_models, write_file
from utils import get_description_models, get_repair_models, get_review_models

from preprocess import Preprocessor

from search import ChromaSearch

from prompt import DescriptionPrompt, RepairPrompt, ReviewPrompt
from response import Response
from patch import Patch

from config import CHROMA_PATH, COLLECTION_NAME, NUM_NEIGHBORS
from config import DESCRIPTION_PROMPT, REPAIR_PROMPT, REVIEW_PROMPT

from pathlib import Path
import argparse


if __name__ == "__main__":
    client = chromadb.PersistentClient(
        path=CHROMA_PATH, settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_collection(name=COLLECTION_NAME)
    searcher = ChromaSearch(collection=collection)

    parser = argparse.ArgumentParser()
    parser.add_argument("source_path")
    parser.add_argument("language")
    parser.add_argument("cwe_id")
    parser.add_argument("line_number")
    parser.add_argument("output_dir")

    # Get args from CLI
    args = parser.parse_args()
    source_path = args.source_path
    language = args.language
    cwe_id = args.cwe_id
    line_number = int(args.line_number)
    output_dir = Path(args.output_dir)

    # Setup output directories
    directories = setup_directories(output_dir)
    output_dir = directories["output_dir"]
    source_dir = directories["source_dir"]

    prompt_dir = directories["prompt_dir"]
    description_prompt_dir = directories["description_prompt_dir"]
    repair_prompt_dir = directories["repair_prompt_dir"]
    review_prompt_dir = directories["review_prompt_dir"]

    description_dir = directories["description_dir"]
    patch_dir = directories["patch_dir"]
    raw_patch_dir = directories["raw_patch_dir"]
    review_dir = directories["review_dir"]

    preprocessor = Preprocessor(file_path=source_path, cwe_id=cwe_id, language=language)
    input_program = preprocessor.process(line_number=line_number)

    source = input_program.processed_source
    file_name = input_program.file_name
    line_number = input_program.line_number

    # Write original and processed source
    original_source_path = Path(source_dir) / f"{file_name}.original_source"
    write_file(text=input_program.original_source, path=original_source_path)
    processed_source_path = Path(source_dir) / f"{file_name}.processed_source"
    write_file(text=input_program.processed_source, path=processed_source_path)

    # Setup models
    DESCRIPTION_MODELS = get_description_models()
    REPAIR_MODELS = get_repair_models()
    REVIEW_MODELS = get_review_models()

    # Get description of vulnerability
    description_prompt = DescriptionPrompt(source_program=input_program)
    description_prompt_path = Path(description_prompt_dir) / f"{file_name}.prompt"
    description_prompt.write(path=description_prompt_path)
    # Filter models by context length
    description_models = filter_models(
        models=DESCRIPTION_MODELS, text=description_prompt.content
    )
    raw_descriptions = batch_call(
        models=description_models,
        user_prompt=description_prompt.content,
        system_prompt=DESCRIPTION_PROMPT,
    )
    descriptions = {}
    for model_id, description in raw_descriptions.items():
        description_response = Response(
            prompt=description_prompt,
            content=description,
            model_id=model_id,
            source_program=input_program,
        )
        description_base = f"{model_id}_{file_name}"
        description_path = Path(description_dir) / f"{description_base}.output"
        description_response.write(path=description_path)
        description_cost_path = (
            Path(description_dir) / f"{description_base}.token_count"
        )
        description_response.write_token_count(path=description_cost_path)
        descriptions[model_id] = description_response.get()

    # Get patch
    neighbors = searcher.search(source=source, cwe_id=cwe_id, count=NUM_NEIGHBORS)
    patches = []
    for describer_id, description in descriptions.items():
        repair_prompt = RepairPrompt(
            source_program=input_program,
            model_id=model_id,
            neighbors=neighbors,
            description=description,
        )
        repair_prompt_path = (
            Path(repair_prompt_dir) / f"{describer_id}_{file_name}.prompt"
        )
        repair_prompt.write(path=repair_prompt_path)
        # Filter models by context length
        repair_models = filter_models(models=REPAIR_MODELS, text=repair_prompt.content)
        raw_patches = batch_call(
            models=repair_models,
            user_prompt=repair_prompt.content,
            system_prompt=REPAIR_PROMPT,
        )
        for model_id, raw_patch in raw_patches.items():
            repair_response = Response(
                prompt=repair_prompt,
                content=raw_patch,
                model_id=model_id,
                source_program=input_program,
            )
            patch_base = f"{describer_id}_{model_id}_{file_name}"
            raw_patch_path = Path(raw_patch_dir) / f"{patch_base}.output"
            repair_response.write(path=raw_patch_path)
            patch_cost_path = Path(raw_patch_dir) / f"{patch_base}.token_count"
            repair_response.write_token_count(path=patch_cost_path)

            patch = Patch(response=repair_response)
            patch_path = Path(patch_dir) / f"{patch_base}.diff"
            patch.write(path=patch_path)

            patches.append(
                {"describer": describer_id, "fixer": model_id, "patch": patch}
            )

    for patch_info in patches:
        describer_id = patch_info["describer"]
        fixer_id = patch_info["fixer"]
        patch = patch_info["patch"]

        review_prompt = ReviewPrompt(source_program=input_program, patch=patch)
        review_prompt_path = Path(review_prompt_dir) / f"{file_name}.prompt"
        review_prompt.write(path=review_prompt_path)
        review_models = filter_models(models=REVIEW_MODELS, text=review_prompt.content)
        raw_reviews = batch_call(
            models=review_models,
            user_prompt=review_prompt.content,
            system_prompt=REVIEW_PROMPT,
        )
        for reviewer_id, raw_review in raw_reviews.items():
            review_response = Response(
                prompt=review_prompt,
                content=raw_review,
                model_id=reviewer_id,
                source_program=input_program,
            )
            review_base = f"review_{reviewer_id}_{describer_id}_{fixer_id}_{file_name}"
            review_path = Path(review_dir) / f"{review_base}.output"
            review_response.write(path=review_path)
            review_cost_path = Path(review_dir) / f"{review_base}.token_count"
            review_response.write_token_count(path=review_cost_path)

            patch = Patch(response=review_response)
            patch_path = Path(patch_dir) / f"{review_base}.diff"
            patch.write(path=patch_path)
