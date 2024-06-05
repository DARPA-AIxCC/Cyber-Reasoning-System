from pathlib import Path
from hermes.core.utils.model import ModelUtils
from hermes.core.utils.metadata import MetadataUtils


class Prompt:
    def __init__(self, source_program) -> None:
        self.source_program = source_program
        self.source = self.source_program.processed_source
        self.cwe_id = self.source_program.cwe_id

    def write_prompt(self, prompt: str, path: Path) -> None:
        MetadataUtils.write_file(text=prompt, path=path, header='Prompt')


class RepairPrompt(Prompt):
    def __init__(
        self,
        source_program,
        model_id,
        neighbors,
        description=None
    ):
        super().__init__(source_program)
        self.model_id = model_id

        self.neighbors = neighbors
        self.description = description

        self.content = self.get()

    def get(self) -> str:
        prompt = f"// Program to fix:\n{self.source}"
        if self.description:
            prompt += f"\n/* {self.description} */"

        if self.neighbors:
            for neighbor in reversed(list(self.neighbors)):
                addition = f"\n// Example fix\n{neighbor}\n"
                candidate = prompt + addition
                if (
                    ModelUtils.count_tokens(
                        self.model_id,
                        candidate
                    ) <= ModelUtils.token_limit(self.model_id)
                ):
                    prompt = candidate
        return prompt

    def write(self, path: Path) -> None:
        self.write_prompt(prompt=self.content, path=path)


class BugDescriptionPrompt(Prompt):
    def __init__(
        self,
        source_program,
        original_description,
        patch_content,
        patch_type
    ):
        super().__init__(source_program)
        self.original_description = original_description
        self.patch_content = patch_content
        self.patch_type = str(patch_type).lower()
        self.content = self.get()

    def get(self) -> str:
        return (
            f"The following program has CWE-ID: {self.cwe_id}.\n"
            f"{self.source}. Here is a description of how it contains the CWE: "
            f"{self.original_description}.\n"
            f"I tried to fix it this way:\n{self.patch_content}.\n"
            f"{MetadataUtils.process_patch_type(self.patch_type)}\n"
            "Can you describe why my patch fails please?"
        )

    def write(self, path: Path):
        prompt = self.content
        self.write_prompt(prompt=prompt, path=path)


class CWEDescriptionPrompt(Prompt):
    def __init__(
        self,
        source_program,
    ):
        super().__init__(source_program)
        self.content = self.get()

    def get(self) -> str:
        return (
            f"The following program has CWE-ID: {self.cwe_id}.\n"
            f"{self.source}. Please describe how this program instantiates "
            f"{self.cwe_id}."
        )

    def write(self, path: Path):
        prompt = self.content
        self.write_prompt(prompt=prompt, path=path)


class ReviewPrompt(Prompt):
    def __init__(self, source_program, patch, description):
        super().__init__(source_program)
        self.patch = patch
        self.patch_content = '\n'.join(self.patch.lines)
        self.description = description
        self.content = self.get()

    def get(self):
        return (
            f"Here is the program: {self.source}\n"
            f"Here is why I think it's vulnerable: {self.description}\n"
            f"And here is my proposed fix: {self.patch_content}"
        )

    def write(self, path: Path):
        self.write_prompt(prompt=self.content, path=path)
