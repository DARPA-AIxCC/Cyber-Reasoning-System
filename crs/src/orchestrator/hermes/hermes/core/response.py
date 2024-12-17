from pathlib import Path

from hermes.core.utils.model import ModelUtils
from hermes.core.utils.metadata import MetadataUtils

from hermes.core.program import Program
from hermes.core.prompt import Prompt
from hermes.log import logger

import re


class Response:
    def __init__(
            self,
            prompt: Prompt,
            content: str,
            model_id: str,
            source_program: Program):
        self.prompt = prompt
        self.content = content
        self.model_id = model_id
        self.source_program = source_program
        self.file_name = self.source_program.file_name

    def get(self) -> str:
        return self.content

    def write(self, path: Path):
        if self.content:
            MetadataUtils.write_file(
                text=self.content,
                path=path,
                header='Response'
            )
        else:
            logger.warning(f'{self.model_id} did not respond. Nothing to write.')
    def get_token_count(self):
        prompt_tokens = ModelUtils.count_tokens(
            model_id=self.model_id,
            text=self.prompt.content
        )
        response_tokens = ModelUtils.count_tokens(
            model_id=self.model_id,
            text=self.content
        )
        return (prompt_tokens, response_tokens)

    def write_token_count(self, path):
        prompt_tokens = ModelUtils.count_tokens(
            model_id=self.model_id,
            text=self.prompt.content
        )
        response_tokens = ModelUtils.count_tokens(
            model_id=self.model_id,
            text=self.content
        )
        report = f'Input: {prompt_tokens}\nOutput: {response_tokens}'
        MetadataUtils.write_file(text=report, path=path)
        return (prompt_tokens, response_tokens)

    def get_code(self):
        """Extract code from the model response.
        Assumes that the code is found between ``` and ```.
        If there are multiple code snippets in the response,
        this will choose the longest snippet.
        This further removes all instances of 'java', 'cpp', 'c++', and 'c'.
        This is done because sometimes the model starts the diff with a
        language identifier.

        Returns
        -------
        [str]
            Filtered string: all contents between ``` and ``` after removing
            'java', 'cpp', 'c++', and 'c'.
            If the response is improperly formatted (i.e. no closing ```), then
            this function will return all text in the response.
        """
        text = self.content
        pattern = r'```(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)

        if matches:
            filtered = max(matches, key=len).splitlines()
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
            logger.warning('Could not find code between three back-ticks.')
            return text.splitlines()
