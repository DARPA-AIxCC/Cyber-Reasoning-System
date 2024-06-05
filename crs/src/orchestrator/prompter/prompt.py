from pathlib import Path
from utils import logger, count_tokens, token_limit


class Prompt:
    def __init__(self, source_program) -> None:
        self.source_program = source_program
        self.source = self.source_program.processed_source
        self.cwe_id = self.source_program.cwe_id

    def write_prompt(self, prompt: str, path: Path) -> None:
        try:
            with path.open("w") as file:
                file.write("-----> Prompt <-----\n")
                file.write(prompt)
            logger.info(f"Successfully wrote prompt to {path}.")
        except Exception as e:
            logger.error(f"An error occurred while writing the file: {e}")


class RepairPrompt(Prompt):
    def __init__(self, source_program, model_id, neighbors, description=None) -> None:
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
                if count_tokens(self.model_id, candidate) <= token_limit(self.model_id):
                    prompt = candidate
        return prompt

    def write(self, path: Path) -> None:
        self.write_prompt(prompt=self.content, path=path)


class DescriptionPrompt(Prompt):
    def __init__(self, source_program) -> None:
        super().__init__(source_program)
        self.content = self.get()

    def get(self) -> str:
        return (
            f"The following program has CWE-ID: {self.cwe_id}.\n"
            f"{self.source}. Please describe how this program instantiates "
            f"{self.cwe_id}."
        )

    def write(self, path: Path) -> None:
        prompt = self.content
        self.write_prompt(prompt=prompt, path=path)


class ReviewPrompt(Prompt):
    def __init__(self, source_program, patch):
        super().__init__(source_program)
        self.patch = patch
        self.patch_content = "\n".join(self.patch.lines)
        self.content = self.get()

    def get(self):
        return (
            f"Here is the program: {self.source}\n"
            f"It has the following CWE: {self.cwe_id}\n"
            f"And here is the candidate patch: {self.patch_content}"
        )

    def write(self, path: Path):
        self.write_prompt(prompt=self.content, path=path)
