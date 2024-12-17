from hermes.core.prompt import (
    CWEDescriptionPrompt,
    BugDescriptionPrompt,
    RepairPrompt,
    ReviewPrompt,
)
from hermes.core.response import Response
from hermes.core.patch import Patch

from hermes.config.config import (
    CWE_DESCRIPTION_PROMPT,
    BUG_DESCRIPTION_PROMPT,
    CWE_REPAIR_PROMPT,
    BUG_REPAIR_PROMPT,
    REVIEW_PROMPT,
    MAX_WORKERS
)
from hermes.core.utils.metadata import MetadataUtils
from hermes.core.utils.model import ModelUtils

from hermes.log import logger

from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed


class BugDescriber:
    def __init__(
        self,
        input_program,
        original_description,
        buggy_patch,
        patch_type,
        description_prompt_dir,
        description_dir,
        description_models,
        quiet=False
    ):
        self.input_program = input_program
        self.original_description = original_description
        self.buggy_patch = buggy_patch
        self.patch_type = patch_type

        self.description_prompt_dir = description_prompt_dir
        self.description_dir = description_dir
        self.description_models = description_models

        self.quiet = quiet

    def get_descriptions(self, cost):
        descriptions = {}
        cost["description"] = {}

        if not self.input_program:
            logger.warning(
                f'{self.input_program} is empty. Skipping BugDescriber step.'
            )
            return descriptions, cost

        logger.info(f"Getting description for {self.input_program}.")

        program_id = self.input_program.program_id
        cost["bug_id"] = program_id

        description_prompt = BugDescriptionPrompt(
            source_program=self.input_program,
            original_description=self.original_description,
            patch_content=self.buggy_patch,
            patch_type=self.patch_type
        )
        if not self.quiet:
            description_prompt_path = (
                Path(self.description_prompt_dir) / f"feedback_{program_id}.prompt"
            )
            description_prompt.write(path=description_prompt_path)
        # Filter models by context length
        filtered_models = ModelUtils.filter_models(
            models=self.description_models, text=description_prompt.content
        )
        raw_descriptions = ModelUtils.batch_call(
            models=filtered_models,
            user_prompt=description_prompt.content,
            system_prompt=BUG_DESCRIPTION_PROMPT,
        )

        for model_id, description in raw_descriptions.items():
            description_response = Response(
                prompt=description_prompt,
                content=description,
                model_id=model_id,
                source_program=self.input_program,
            )
            description_base = f"{model_id}_{program_id}"
            if not self.quiet:
                description_path = (
                    Path(self.description_dir) /
                    f"feedback_{description_base}.output"
                )
                description_response.write(path=description_path)
                # Get description cost
                prompt_tokens, \
                    response_tokens = description_response.get_token_count()
                cost["description"][model_id] = {
                    "input": prompt_tokens,
                    "output": response_tokens,
                }
            descriptions[model_id] = description_response.get()
        return descriptions, cost


class CWEDescriber:
    def __init__(
        self,
        input_program,
        description_prompt_dir,
        description_dir,
        description_models,
        quiet=False
    ):
        self.input_program = input_program
        self.description_prompt_dir = description_prompt_dir
        self.description_dir = description_dir
        self.description_models = description_models
        self.quiet = quiet

    def get_descriptions(self, cost):
        descriptions = {}
        cost["description"] = {}

        if not self.input_program:
            logger.warning(
                f'{self.input_program} is empty. Skipping CWEDescriber step.'
            )
            return descriptions, cost
        program_id = self.input_program.program_id
        cost["bug_id"] = program_id

        # Get description of vulnerability
        logger.info(f"Getting description for {self.input_program}.")
        description_prompt = CWEDescriptionPrompt(
            source_program=self.input_program
        )
        if not self.quiet:
            description_prompt_path = (
                Path(self.description_prompt_dir) /
                f"{program_id}.prompt"
            )
            description_prompt.write(path=description_prompt_path)
        # Filter models by context length
        filtered_models = ModelUtils.filter_models(
            models=self.description_models, text=description_prompt.content
        )
        raw_descriptions = ModelUtils.batch_call(
            models=filtered_models,
            user_prompt=description_prompt.content,
            system_prompt=CWE_DESCRIPTION_PROMPT,
        )

        for describer_id, description in raw_descriptions.items():
            description_response = Response(
                prompt=description_prompt,
                content=description,
                model_id=describer_id,
                source_program=self.input_program,
            )
            str_describer_id = describer_id.replace('/', '-')
            description_base = f"Describer-{str_describer_id}_{program_id}"
            description_path = (
                Path(self.description_dir) / f"{description_base}.output"
            )
            if not self.quiet:
                description_response.write(path=description_path)
                # Get description cost
                prompt_tokens, \
                    response_tokens = description_response.get_token_count()
                cost["description"][describer_id] = {
                    "input": prompt_tokens,
                    "output": response_tokens,
                }
            descriptions[describer_id] = description_response.get()
        return descriptions, cost


class Fixer:
    def __init__(
        self,
        input_program,
        neighbors,
        repair_models,
        repair_prompt_dir,
        raw_patch_dir,
        patch_dir,
        output_dir,
        quiet=False
    ):
        """A Fixer takes in a program, its neighbors, and repair models.
        Its job is to produce fixes for the input program using the neighbors,
        by making calls to the repair models.

        Parameters
        ----------
        input_program : [Program]
            A program object. This should represent the program to be repaired.
        neighbors : [List[str]]
            Each item in the list is treated as a neighbor, and all neighbors
            are passed to the RepairPrompt to dynamically add as many as
            a given repair model can accept.
            Excpected neighbor is a diff, but because of Python's duck-typing,
            anything would work here.
        repair_models : [List[str]]
            A list of model_id's to use to generate patches.
            These model_id's are expected to be valid model_id's that
            the current environment has keys for.
            No validation is done here to save time.
        repair_prompt_dir : [pathlib.Path]
            Path to store repair prompts.
            Since different models have different limits, the repair prompts
            can differ in the number of neighbors included even when the
            description used is the same.
        raw_patch_dir : [pathlib.Path]
            Path to store raw outputs from the repair models.
        patch_dir : [pathlib.Path]
            Path to store diffs obtained after processing the raw outputs.
        output_dir : [pathlib.Path]
            Path inside which all the metadata (prompts, raw outputs, cost)
            should be stored.
        quiet : [bool]
            If True, intermediate prompts and raw responses won't be written.
            False by default.
        """
        self.input_program = input_program
        self.neighbors = neighbors
        self.repair_models = repair_models

        self.repair_prompt_dir = repair_prompt_dir
        self.raw_patch_dir = raw_patch_dir
        self.patch_dir = patch_dir
        self.output_dir = output_dir

        self.quiet = quiet

    def run_once(
        self,
        fixer_id,
        describer_id,
        description,
        cost,
        feedback=False
    ):
        """Call one fixer on one description.

        Parameters
        ----------
        fixer_id : [str]
        describer_id : [str]
        description : [str]
            Description of the bug
        cost : [dict]
            Dict to use to store the cost of running the fixer.
        feedback : bool, optional
            Determine which system prompt to use.
            If True:
            -   Use the Bug Repair Prompt, where the goal is to fix
            a buggy patch.
            Otherwise:
            -   Use the CWE Repair Prompt, where the goal is to fix
            a vulnerability.

        Returns
        -------
        [dict]
            {
                "cwe_id": [str],
                "processed_source": [str],
                "describer_id": [str],
                "description": [str],
                "fixer_id": [str],
                "patch": [Patch],
                "patch_path": [pathlib.Path]
            }
        """
        program_id = self.input_program.program_id
        str_fixer_id = fixer_id.replace('/', '-')
        str_describer_id = describer_id.replace('/', '-')

        patch_base = (
            f"Fixer-{str_fixer_id}_Describer-{str_describer_id}_{program_id}"
        )

        repair_prompt = RepairPrompt(
            source_program=self.input_program,
            model_id=fixer_id,
            neighbors=self.neighbors,
            description=description,
        )
        if not self.quiet:
            repair_prompt_path = (
                Path(self.repair_prompt_dir) / f"{patch_base}.prompt"
            )
            repair_prompt.write(path=repair_prompt_path)

        logger.info(
            f'Getting patch from (Fixer: {fixer_id}, '
            f'Describer: {describer_id}).'
        )
        raw_patch = ModelUtils.call_model(
            model_id=fixer_id,
            user_prompt=repair_prompt.content,
            system_prompt=BUG_REPAIR_PROMPT if feedback else CWE_REPAIR_PROMPT,
        )
        repair_response = Response(
            prompt=repair_prompt,
            content=raw_patch,
            model_id=fixer_id,
            source_program=self.input_program,
        )

        # Save raw fixer model output and cost of repair
        if not self.quiet:
            raw_patch_path = Path(self.raw_patch_dir) / f"{patch_base}.output"
            repair_response.write(path=raw_patch_path)

            # Get repair cost
            prompt_tokens, response_tokens = repair_response.get_token_count()
            cost["repair"][fixer_id] = {
                f"{describer_id}": {
                    "input": prompt_tokens,
                    "output": response_tokens
                }
            }

        # Process generated patch and save to disk
        patch = Patch(response=repair_response)
        patch_path = Path(self.patch_dir) / f"{patch_base}.diff"
        patch.write(path=patch_path)
        return {
            "cwe_id": self.input_program.cwe_id,
            "processed_source": self.input_program.processed_source,
            "describer_id": describer_id,
            "description": description,
            "fixer_id": fixer_id,
            "patch": patch,
            "patch_path": patch_path
        }

    def process_description(self, describer_id, description, cost, feedback):
        """Send a single description to the helper.

        Parameters
        ----------
        fixer_id : [str]
        describer_id : [str]
        description : [str]
            Description of the bug
        cost : [dict]
            Dict to use to store the cost of running the fixer.
        feedback : bool, optional
            Determine which system prompt to use.
            If True:
            -   Use the Bug Repair Prompt, where the goal is to fix
            a buggy patch.
            Otherwise:
            -   Use the CWE Repair Prompt, where the goal is to fix
            a vulnerability.
        """
        return self.helper(
            describer_id=describer_id,
            description=description,
            cost=cost,
            feedback=feedback
        )

    def helper(self, describer_id, description, cost, feedback):
        """Get patches by giving a single description to all repair models.
        This is done separately (without using ModelUtils.batch_call()) to
        make it easier to track the running costs.

        Parameters
        ----------
        fixer_id : [str]
        describer_id : [str]
        description : [str]
            Description of the bug
        cost : [dict]
            Dict to use to store the cost of running the fixer.
        feedback : bool, optional
            Determine which system prompt to use.
            If True:
            -   Use the Bug Repair Prompt, where the goal is to fix
            a buggy patch.
            Otherwise:
            -   Use the CWE Repair Prompt, where the goal is to fix
            a vulnerability.

        Returns
        -------
        [List[dict]]
            A list of dicts as returned by Fixer.run_once()
        """
        logger.info(
            f'Getting patch from the description generated by {describer_id}.'
        )
        patches = []
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_fixer = {
                executor.submit(
                    self.run_once,
                    fixer_id,
                    describer_id,
                    description,
                    cost,
                    feedback
                ): fixer_id
                for fixer_id in self.repair_models
            }
            for future in as_completed(future_to_fixer):
                fixer_id = future_to_fixer[future]
                try:
                    patch = future.result()
                    patches.append(patch)
                except Exception as exc:
                    print(f"Fixer {fixer_id} generated an exception: {exc}")

        return patches

    def get_patch(self, descriptions, cost, feedback=False):
        """Get patches by giving each description in descriptions to all
        the repair models.
        In essence, this parallelizes the handing off of descriptions to
        self.helper().
        This isn't done using ModelUtils.batch_call() for two reasons:
        -   First, because the descriptions aren't the same (not one-to-many)
        -   Second, to facilitate tracking the running cost

        Parameters
        ----------
        descriptions : [dict]
            A dict to contain all the descriptions.
            {
                describer_id [str]: description [str]
            }
        cost : [dict]
            Dict to use to store the cost of running the fixer.

        feedback : bool, optional
            Determine which system prompt to use.
            If True:
            -   Use the Bug Repair Prompt, where the goal is to fix
            a buggy patch.
            Otherwise:
            -   Use the CWE Repair Prompt, where the goal is to fix
            a vulnerability.

        Returns
        -------
        [List[dict]]
            A list of dicts, where each dict contains some information about
            the generated patches. Check Fixer.run_once() for more details.
        """
        cost["repair"] = {}
        patches = []
        if not self.input_program:
            logger.warning(
                f'{self.input_program} is empty. Skipping Fixer step.'
            )
            return patches

        logger.info(
            f'Getting patches from {len(descriptions)} '
            f'description{"s" if len(descriptions) != 1 else ""}.'
        )
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_description = {
                executor.submit(
                    self.process_description,
                    describer_id,
                    description,
                    cost,
                    feedback
                ): describer_id
                for describer_id, description in descriptions.items()
            }

            for future in as_completed(future_to_description):
                describer_id = future_to_description[future]
                try:
                    patch_batch = future.result()
                    patches += patch_batch
                except Exception as exc:
                    logger.warning(
                        f"Description from {describer_id} "
                        f"generated an exception: {exc}"
                    )

        program_id = self.input_program.program_id
        if not self.quiet:
            cost_path = Path(self.output_dir) / f"{program_id}_cost.json"
            MetadataUtils.dump_dict(data=cost, path=cost_path)
        return patches


class Reviewer:
    def __init__(
        self,
        input_program,
        review_models,
        review_prompt_dir,
        review_dir,
        patch_dir,
        output_dir,
        quiet=False
    ):
        self.input_program = input_program
        self.review_models = review_models

        self.review_prompt_dir = review_prompt_dir
        self.review_dir = review_dir
        self.patch_dir = patch_dir
        self.output_dir = output_dir

        self.quiet = quiet

    def helper(self, patch_info, cost):
        program_id = self.input_program.program_id
        describer_id = patch_info["describer_id"]
        fixer_id = patch_info["fixer_id"]
        patch = patch_info["patch"]
        description = patch_info['description']

        str_describer_id = describer_id.replace('/', '-')
        str_fixer_id = fixer_id.replace('/', '-')

        review_prompt = ReviewPrompt(
            source_program=self.input_program,
            patch=patch,
            description=description
        )
        if not self.quiet:
            review_prompt_path = (
                Path(self.review_prompt_dir) /
                f"Fixer-{str_fixer_id}_Describer-{str_describer_id}_{program_id}.prompt"
            )
            review_prompt.write(path=review_prompt_path)
        filtered_models = ModelUtils.filter_models(
            models=self.review_models, text=review_prompt.content
        )
        raw_reviews = ModelUtils.batch_call(
            models=filtered_models,
            user_prompt=review_prompt.content,
            system_prompt=REVIEW_PROMPT,
        )
        patches = []
        for reviewer_id, raw_review in raw_reviews.items():
            review_response = Response(
                prompt=review_prompt,
                content=raw_review,
                model_id=reviewer_id,
                source_program=self.input_program,
            )
            str_reviewer_id = reviewer_id.replace('/', '-')
            review_base = (
                f"Reviewer-{str_reviewer_id}_Fixer-{str_fixer_id}_"
                f"Describer-{str_describer_id}_{program_id}"
            )
            if not self.quiet:
                review_path = Path(self.review_dir) / f"{review_base}.output"
                review_response.write(path=review_path)
                prompt_tokens, \
                    response_tokens = review_response.get_token_count()
                if reviewer_id not in cost["review"]:
                    cost["review"][reviewer_id] = {}
                if fixer_id not in cost["review"][reviewer_id]:
                    cost["review"][reviewer_id][fixer_id] = {}
                cost["review"][reviewer_id][fixer_id][describer_id] = {
                    "input": prompt_tokens,
                    "output": response_tokens,
                }

            reviewed_patch = Patch(response=review_response)
            if reviewed_patch != patch:
                patch_path = Path(self.patch_dir) / f"{review_base}.diff"
                reviewed_patch.write(path=patch_path)
                patches.append(
                    {
                        "cwe_id": self.input_program.cwe_id,
                        "processed_source": self.input_program.processed_source,
                        "describer_id": describer_id,
                        "description": description,
                        "fixer_id": fixer_id,
                        "patch": reviewed_patch,
                        "patch_path": patch_path,
                        "reviewer_id": reviewer_id
                    }
                )
            else:
                logger.info(f"Review by {reviewer_id} produced same patch.")
        return patches

    def get_reviews(self, patches, cost):
        cost["review"] = {}
        reviewed_patches = []

        if not self.input_program:
            logger.warning(
                f'{self.input_program} is empty. Skipping Review step.'
            )
            return reviewed_patches

        logger.info(f"Getting reviews for {self.input_program}.")
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(self.helper, patch_info, cost)
                for patch_info in patches
            ]
            for future in as_completed(futures):
                try:
                    patch_batch = future.result()
                    reviewed_patches += patch_batch
                except Exception as e:
                    logger.warning(f"Review produced {e}.")

        program_id = self.input_program.program_id
        if not self.quiet:
            cost_path = Path(self.output_dir) / f"{program_id}_cost.json"
            MetadataUtils.dump_dict(data=cost, path=cost_path)
        return reviewed_patches
