from pathlib import Path

from utils import logger, count_tokens, write_file

from program import Program
from prompt import Prompt


class Response:
    def __init__(
        self, prompt: Prompt, content: str, model_id: str, source_program: Program
    ):
        self.prompt = prompt
        self.content = content
        self.model_id = model_id
        self.source_program = source_program
        self.file_name = self.source_program.file_name

    def get(self) -> str:
        return self.content

    def write(self, path: Path) -> None:
        try:
            with open(path, "w") as file:
                file.write((self.content))
            logger.info(f"Successfully wrote raw response: {path}")
        except Exception as e:
            logger.warn(f"An error occurred while writing the file: {e}")

    def write_token_count(self, path):
        prompt_tokens = count_tokens(model_id=self.model_id, text=self.prompt.content)
        response_tokens = count_tokens(model_id=self.model_id, text=self.content)
        report = f"Input: {prompt_tokens}\nOutput: {response_tokens}"
        write_file(text=report, path=path)
        return (prompt_tokens, response_tokens)

    def get_code(self):
        """Extract code from the model response.
        Assumes that the code is found between ``` and ```.
        This further removes all instances of 'java', 'cpp', 'c++', and 'c'. This
        is done because sometimes the model starts the diff with a language
        identifier.

        Parameters
        ----------
        text : [str]
            Raw model response as a string.

        Returns
        -------
        [str]
            Filtered string: all contents between ``` and ``` after removing
            'java', 'cpp', 'c++', and 'c'.
            If the response is improperly formatted (i.e. no closing ```), then
            this function will return all text after the first ```.
        """
        start = "```"
        end = "```"
        text = self.content
        filtered = text[text.find(start) + len(start) : text.rfind(end)]

        if filtered:
            filtered = filtered.splitlines()
            filtered = [
                line
                for line in filtered
                if (
                    (line != "java")
                    & (line != "```java")
                    & (line != "cpp")
                    & (line != "```cpp")
                    & (line != "c++")
                    & (line != "```c++")
                    & (line != "c")
                    & (line != "```c")
                )
            ]
            return "\n".join(filtered).splitlines()
        else:
            return text[text.find(start) + len(start) :].splitlines()
