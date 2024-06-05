from typing import Dict, List, Optional
from tree_sitter import Language, Parser, Node

from pathlib import Path

import tree_sitter_python as tspython
import tree_sitter_cpp as tscpp
import tree_sitter_c as tsc
import tree_sitter_java as tsjava

from program import Program
from utils import logger


class TreeSitter:
    def __init__(self, source: str, file_path: Path, cwe_id: str, language: str):
        self.source: str = source
        self.file_path = file_path
        self.cwe_id = cwe_id

        self.language: str = language.lower()
        if self.language not in self.supported_languages():
            raise ValueError(f"{self.language} is not in {self.supported_languages()}.")

        self.parser: Parser = self.supported_parsers()[self.language]
        self.tree = self.parser.parse(bytes(self.source, "utf-8"))

    @staticmethod
    def supported_languages() -> List[str]:
        return list(TreeSitter.supported_parsers().keys())

    @staticmethod
    def supported_parsers() -> Dict[str, Parser]:
        return {
            "python": Parser(Language(tspython.language())),
            "cpp": Parser(Language(tscpp.language())),
            "c++": Parser(Language(tscpp.language())),
            "c": Parser(Language(tsc.language())),
            "java": Parser(Language(tsjava.language())),
        }

    def search_wrapper(self, line_number: int) -> Optional[Node]:
        candidates = self.get_context(line_number=line_number)
        function_node = [
            candidate
            for candidate in candidates
            if candidate.type
            in ["method_declaration", "function_definition", "function_declarator"]
        ]

        if not function_node:
            print(f"Could not find function surrounding line {line_number}.")
            return candidates[0]
        return function_node[0]

    def get_context(self, line_number: int):
        candidates = []

        def traverse(n):
            if n.start_point.row <= line_number <= n.end_point.row:
                candidates.append(n)
            for child in n.children:
                traverse(child)

        traverse(self.tree.root_node)

        filtered_candidates = [
            candidate
            for candidate in candidates
            if (
                candidate.type
                in [
                    "block",
                    "method_declaration",
                    "function_definition",
                    "function_declarator",
                    "if_statement",
                    "case_statement",
                    "compound_statement",
                    "switch_statement",
                    "class_body",
                    "class_declaration",
                ]
            )
        ]
        if not filtered_candidates:
            return candidates
        return filtered_candidates

    def get_lines(self, node: Node, line_numbers: bool) -> List[str]:
        lines = "".join(node.text.decode("utf-8")).split("\n")
        if line_numbers:
            lines = [
                f"{node.start_point.row + idx}: {line}"
                for idx, line in enumerate(lines)
            ]
        return Program(
            original_source=self.source,
            file_path=self.file_path,
            cwe_id=self.cwe_id,
            lines=lines,
            line_number=int(node.start_point.row),
        )


class Preprocessor:
    def __init__(self, file_path, cwe_id, language):
        self.file_path = Path(file_path)
        if not self.file_path.is_file():
            raise TypeError("The provided path does not point to a file.")

        try:
            with open(self.file_path, "r") as file:
                self.source = file.read()
            self.lines = self.source.split("\n")
            logger.info(f"Successfully read {self.file_path}.")
        except Exception as e:
            logger.warn(f"An error occurred while reading the file: {e}.")

        self.cwe_id = cwe_id
        self.language = language

    def process(self, line_number):
        """Process source code.
        Supports multiple options:
            -   If [line_numer] is None, returns unmodified source
            -   Otherwise:
                -   extracts the function inside which the line is located

        Parameters
        ----------
        line_number : [int]
            Number of the buggy line

        Returns
        -------
        [Program]
            -   Program object with the following attributes:
                -   source: the whole source code
                -   file_path: path of the file for the source code
                -   cwe_id: CWE ID of the vulnerability
                    -   if [line_number] is given:
                        -   candidates: list of candidates, where each
                            candidate is a trimmed-down version of the source
                    -   otherwise:
                        -   candidates: empty list

        Raises
        ------
        ValueError
            If requested line isn't inside a function, throw a ValueError
        """
        helper = TreeSitter(
            source=self.source,
            file_path=self.file_path,
            cwe_id=self.cwe_id,
            language=self.language,
        )
        # Get node for the context
        result = helper.search_wrapper(line_number=line_number)

        if result:
            return helper.get_lines(node=result, line_numbers=False)
        else:
            raise ValueError(f"Unable to find function for line {line_number}")
