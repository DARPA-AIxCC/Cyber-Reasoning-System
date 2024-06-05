from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from collections import defaultdict, deque
from collections.abc import Generator
from dataclasses import dataclass
from functools import cache
from itertools import chain, zip_longest
from os import PathLike
from os.path import isfile
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any

import click
import tree_sitter_java as tsjava
from litellm import completion
from tree_sitter import Language
from tree_sitter import Node as TSNode
from tree_sitter import Parser, Tree
from tss.aicc.slice import Slicer

JAVA_LANGUAGE = Language(tsjava.language())

CALL_GRAPH_GENERATOR_JAR = str(
    Path(__file__)
    .resolve()
    .parent.parent.parent.joinpath(
        "call-graph-generator", "target", "call-graph-generator.jar"
    )
)
assert isfile(CALL_GRAPH_GENERATOR_JAR), f"{CALL_GRAPH_GENERATOR_JAR} is not a file"


HOOKS = {
    "OsCommandInjection": {
        "conditions": ['Arrays.asList(new String[]{cmd}).contains("jazze")']
    }
}

ENTRY = dict(
    qualifiedClassName="PipelineCommandUtilPovRunner",
    methodName="fuzzerTestOneInput",
    argTypes=["byte[]"],
    argNames=["data"],
)


@dataclass
class Predicate:
    ts_node: TSNode
    is_true: bool

    def description(self) -> str:
        truth_value = "true" if self.is_true else "false"
        return f"({self.ts_node.text.decode()}) == {truth_value}"


@dataclass
class CgNode:
    qualifiedClassName: str
    methodName: str
    argTypes: list[str]
    argNames: list[str]

    def __str__(self) -> str:
        arg_list = ", ".join(f"{t} {n}" for t, n in zip(self.argTypes, self.argNames))
        return f"{self.qualifiedClassName}::{self.methodName}({arg_list})"

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, CgNode)
            and self.qualifiedClassName == other.qualifiedClassName
            and self.methodName == other.methodName
            and self.argTypes == other.argTypes
        )

    def __hash__(self) -> int:
        return hash((self.qualifiedClassName, self.methodName, tuple(self.argTypes)))


@dataclass(eq=True, frozen=True)
class FilePos:
    line: int
    endLine: int
    column: int
    endColumn: int
    start: int
    end: int
    file: str

    def to_tsnode(self) -> TSNode | None:
        pos = self
        content = cached_read_file(pos.file)

        parser = Parser()
        parser.set_language(JAVA_LANGUAGE)
        tree = parser.parse(content)

        for tsnode in self.traverse_tree(tree):
            if tsnode.start_byte == pos.start and tsnode.end_byte == pos.end:
                return tsnode

        print(
            f"Warning: failed to find a treesitter node at: {pos.file}, bytes [{pos.start}, {pos.end})",
            file=sys.stderr,
        )
        return None

    @staticmethod
    def traverse_tree(tree: Tree) -> Generator[TSNode, None, None]:
        cursor = tree.walk()

        visited_children = False
        while True:
            if not visited_children:
                yield cursor.node
                if not cursor.goto_first_child():
                    visited_children = True
            elif cursor.goto_next_sibling():
                visited_children = False
            elif not cursor.goto_parent():
                break


@dataclass
class CfgPath:
    node: CgNode
    position: FilePos
    predicates: list[Predicate]

    def add_predicate(self, predicate: Predicate) -> None:
        self.predicates.append(predicate)

    def get_predicate_dependencies(
        self, index: int, slicer: Slicer, arg_map: dict[str, str]
    ) -> list[str]:
        """Get the string representations of the dependencies of a predicate.

        Args:
            index: index of predicate
            slicer: slicer
            arg_map: mapping from formal parameter names to actual arguments for this method call

        Returns:
            list of string representations of the dependencies
        """
        result = []

        predicate = self.predicates[index]

        content = cached_read_file(self.position.file).decode().splitlines()
        line_numbers = self._get_dependent_line_numbers(predicate, slicer)

        result.extend(content[line_no] for line_no in line_numbers)

        return result

    def _get_dependent_line_numbers(
        self, predicate: Predicate, slicer: Slicer
    ) -> list[int]:
        predicate_line_no, _ = predicate.ts_node.start_point
        method_name = self.node.methodName

        ddg = slicer.slice(self.position.file, method_name, predicate_line_no)

        line_numbers = set()

        for x in ddg:
            the_type, predicate_line_no = self._parse_ddg_tag(x)
            if the_type in ["METHOD", "PARAM"]:
                continue

            line_numbers.add(predicate_line_no)

        line_numbers.discard(predicate_line_no)
        return sorted(line_numbers)

    @classmethod
    def _parse_ddg_tag(cls, tag: str) -> tuple[str, int]:
        pattern = r"<\((.*?),(.*)<SUB>(\d+)</SUB>>"

        if match := re.match(pattern, tag):
            return match[1], int(match[3])

        raise RuntimeError(f"cannot parse ddg result: {tag}")


def find_identifiers(tsnode: TSNode) -> list[str]:
    identifiers = []
    for child in tsnode.children:
        if child.type == "identifier":
            identifiers.append(child.text.decode())
        else:
            identifiers.extend(find_identifiers(child))
    return list(set(identifiers))


@dataclass
class Constraint:
    predicate_desc: str
    dependencies: list[str]


@dataclass
class IcfgPath:
    arg_maps: list[dict[str, str]]
    cfg_paths: list[CfgPath]

    hook_name: str
    hook_arg_map: dict[str, str]

    def compute_description(self, slicer: Slicer) -> str:
        return self._describe_constraints(
            [*self._collect_path_constraints(slicer), *self._collect_hook_constraints()]
        )

    def _collect_hook_constraints(self) -> list[Constraint]:
        constraints = []

        parser = Parser()
        parser.set_language(JAVA_LANGUAGE)
        for predicate_desc in HOOKS[self.hook_name]["conditions"]:
            dependencies = []

            ts_node = parser.parse(predicate_desc.encode()).root_node
            identifiers = find_identifiers(ts_node)
            for ident in identifiers:
                if arg := self.hook_arg_map.get(ident):
                    dependencies.append(f"{ident} == {arg}")

            constraints.append(Constraint(predicate_desc, dependencies))

        return constraints

    def _collect_path_constraints(self, slicer: Slicer) -> list[Constraint]:
        result = []

        for arg_map, path in zip(self.arg_maps, self.cfg_paths):
            param_deps = [f"{param} == {arg}" for param, arg in arg_map.items()]
            result.append(Constraint("", param_deps))

            for idx, predicate in enumerate(path.predicates):
                dependencies = path.get_predicate_dependencies(idx, slicer, arg_map)
                if not dependencies:
                    print(
                        f"warning: failed to find dependencies of predicate: {predicate.ts_node.text.decode()}",
                        file=sys.stderr,
                    )
                result.append(Constraint(predicate.description(), dependencies))

        return result

    @classmethod
    def _describe_constraints(cls, constraints: list[Constraint]) -> str:
        predicates_s = "\n&& ".join(
            c.predicate_desc for c in constraints if c.predicate_desc
        )

        lines = [cls._markdown_code_block(predicates_s)]

        dep_strs = [
            cls._markdown_code_block("\n".join(c.dependencies))
            for c in constraints
            if c.dependencies
        ]
        lines.extend(["", "where", "", "\n\nand\n\n".join(dep_strs)])

        return "\n".join(lines)

    @staticmethod
    def _markdown_code_block(text: str, language: str = "") -> str:
        return f"```{language}\n{text}\n```"


@cache
def find_predicates(tsnode: TSNode) -> list[Predicate]:
    """Find the predicates that guard tsnode."""

    predicates = []
    parent = tsnode
    child = None
    while parent.type != "method_declaration":
        child = parent
        parent = parent.parent

        if parent is None:
            break

        assert child is not None

        if parent.type == "if_statement":
            condition = parent.child_by_field_name("condition")
            assert condition is not None
            expression = condition.child(1)
            assert expression is not None

            if parent.child_by_field_name("consequence") == child:
                predicates.append(Predicate(expression, True))
            else:
                assert parent.child_by_field_name("alternative") == child
                predicates.append(Predicate(expression, False))

    return list(reversed(predicates))  # put outer predicate first


@cache
def cached_read_file(file: str) -> bytes:
    return Path(file).read_bytes()


@dataclass(eq=True, frozen=True)
class CgEdge:
    caller: str
    callee: str
    position: FilePos


@dataclass(eq=True, frozen=True)
class HookTarget:
    node: CgNode
    position: FilePos
    hookName: str


@dataclass
class CallGraph:
    nodes: dict[str, CgNode]
    edges: list[CgEdge]
    hookTargets: list[HookTarget]

    def merge_unknown_nodes(self) -> CallGraph:
        def key(item: tuple[str, CgNode]) -> int:
            _, node = item
            return self.count_unknowns_in_node(node)

        groups = self.group_nodes_by_equality()

        for group in groups:
            group.sort(key=key)

        nodes = dict(group[0] for group in groups)

        label_map = {}
        for group in groups:
            label, _ = group[0]
            for k, _ in group:
                label_map[k] = label

        for k, v in label_map.items():
            if k != v:
                print("call graph: will merge node", k, "into", v)

        edges = [
            CgEdge(
                caller=label_map[e.caller],
                callee=label_map[e.callee],
                position=e.position,
            )
            for e in self.edges
        ]

        return CallGraph(nodes, edges, self.hookTargets)

    def group_nodes_by_equality(self) -> list[list[tuple[str, CgNode]]]:
        groups = []
        for k, v in self.nodes.items():
            for group in groups:
                _, node = group[0]
                if self.node_equal_with_unknown(v, node):
                    group.append((k, v))
                    break
            else:
                groups.append([(k, v)])
        return groups

    @staticmethod
    def node_equal_with_unknown(n: CgNode, m: CgNode) -> bool:
        UNKNOWN = "<UNKNOWN>"

        def str_eq_with_unknown(s1: str, s2: str) -> bool:
            return UNKNOWN in (s1, s2) or (s1 == s2)

        def list_eq_with_unknown(l1: list[str], l2: list[str]) -> bool:
            unknown_list = [UNKNOWN]

            if l1 != unknown_list and l2 != unknown_list:
                return l1 == l2

            return all(
                str_eq_with_unknown(t1, t2)
                for t1, t2 in zip_longest(n.argTypes, m.argTypes, fillvalue=UNKNOWN)
            )

        return (
            str_eq_with_unknown(n.qualifiedClassName, m.qualifiedClassName)
            and str_eq_with_unknown(n.methodName, m.methodName)
            and list_eq_with_unknown(n.argTypes, m.argTypes)
        )

    @staticmethod
    def count_unknowns_in_node(node: CgNode) -> Any:
        unknown = "<UNKNOWN>"
        return (
            (node.qualifiedClassName == unknown)
            + (node.methodName == unknown)
            + sum(x == unknown for x in node.argTypes)
        )

    def get_arg_map(self, edge: CgEdge) -> dict[str, str]:
        args = []

        tsnode = edge.position.to_tsnode()
        assert tsnode

        params = self.nodes[edge.caller].argNames

        if len(args) == len(params):
            return dict(zip(params, args))

        print(
            f"warning: failed to find out argument mapping of edge {edge}",
            file=sys.stderr,
        )
        return {}


@click.command()
@click.option(
    "-l",
    "--source-list-file",
    type=click.Path(exists=True),
    required=True,
    help="file that lists source files to analyze, one per line",
)
@click.option("-d", "--output-dir", type=click.Path(), required=True)
@click.option(
    "-j",
    "--num-processes",
    type=int,
    default=4,
    help="number of parallel joern processes to use",
)
@click.option(
    "-i", "--inputs", type=int, default=3, help="number of tries to generate an input"
)
def main(
    source_list_file: str | PathLike,
    output_dir: str | PathLike,
    num_processes: int,
    inputs: int,
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    entry = CgNode(**ENTRY)

    raw_cg_str = generate_call_graph_str(source_list_file)
    raw_cg = loads_call_graph(raw_cg_str)
    raw_cg_file = Path(output_dir, "raw_cg.json")
    raw_cg_file.write_text(raw_cg_str)

    cg = raw_cg.merge_unknown_nodes()

    icfg_paths = list(
        chain.from_iterable(
            find_icfg_paths(cg, entry, target) for target in cg.hookTargets
        )
    )

    prompts = []

    sources = Path(source_list_file).read_text().splitlines()
    dots_dir = Path(output_dir, "ddg-dots")
    slicer = Slicer(sources, dots_dir, num_processes)

    for i_path in icfg_paths:
        desc = i_path.compute_description(slicer)
        prompts.append(formulate_prompt(entry.argNames[0], entry.argTypes[0], desc))

    prompts_path = output_dir.joinpath("prompts.json")
    prompts_path.write_text(json.dumps(prompts, indent=4))
    print(f"Dumped generated prompts to {prompts_path}")

    inputs_path = output_dir.joinpath("inputs")
    inputs_path.mkdir(exist_ok=True)
    for prompt_idx, prompt in enumerate(prompts):
        for bin_idx in range(inputs):
            print(f"Trying to generate input {bin_idx} from prompt {prompt_idx}")
            bin = query_llm_and_run_response(prompt)

            if bin is None:
                continue

            bin_path = inputs_path.joinpath(f"{prompt_idx}_{bin_idx}.bin")
            bin_path.write_bytes(bin)


def find_icfg_paths(cg: CallGraph, entry: CgNode, target: HookTarget) -> list[IcfgPath]:
    call_graph_paths = find_call_sequences_to_target(cg, entry, target)

    icfg_paths = []

    for edges in call_graph_paths:
        cfg_paths = []
        arg_maps = []

        args = []
        for edge in edges:
            tsnode = edge.position.to_tsnode()
            assert tsnode

            arg_map = {}
            params = cg.nodes[edge.caller].argNames
            if len(args) == len(params):
                arg_map = dict(zip(params, args))
            else:
                print(
                    f"warning: failed to find out argument mapping of edge {edge}",
                    file=sys.stderr,
                )
                arg_map = {}
            arg_maps.append(arg_map)

            args = get_arguments(tsnode)

            predicates = find_predicates(tsnode)
            caller = cg.nodes[edge.caller]
            ast_path = CfgPath(caller, edge.position, predicates)

            cfg_paths.append(ast_path)

        assert cg.nodes[edges[-1].callee] == target.node
        params = target.node.argNames
        assert len(args) == len(params)
        hook_arg_map = dict(zip(params, args))

        icfg_paths.append(IcfgPath(arg_maps, cfg_paths, target.hookName, hook_arg_map))

    return icfg_paths


def get_arguments(tsnode: TSNode) -> list[str]:
    if tsnode.type == "method_invocation":
        invocation = tsnode
    else:
        # CtInvocation in Spoon may be an expression statement
        assert tsnode.type == "expression_statement"

        invocation = tsnode.child(0)
        assert invocation

    arg_list = invocation.child_by_field_name("arguments")
    assert arg_list

    args = [arg.text.decode() for arg in arg_list.children]
    exclude = ("(", ")", ",")
    return [arg for arg in args if arg not in exclude]


def generate_call_graph_str(file_list: str | PathLike) -> str:
    command = [
        "java",
        "-jar",
        CALL_GRAPH_GENERATOR_JAR,
        "-l",
        str(file_list),
    ]

    try:
        cp = subprocess.run(command, capture_output=True, text=True, check=True)
        return cp.stdout
    except subprocess.CalledProcessError as e:
        print("failed to generate call graph:", e.stderr, file=sys.stderr)
        raise


def loads_call_graph(s: str) -> CallGraph:
    cg_data = json.loads(s)
    nodes = {k: CgNode(**v) for k, v in cg_data["nodes"].items()}

    edges = []
    for edge_data in cg_data["edges"]:
        position = FilePos(**edge_data["position"])
        edge = CgEdge(
            caller=edge_data["caller"], callee=edge_data["callee"], position=position
        )
        edges.append(edge)

    hook_targets = []
    for x in cg_data["hookTargets"]:
        node = CgNode(**x["node"])
        position = FilePos(**x["position"])
        hook_targets.append(HookTarget(node, position, x["hookName"]))
    return CallGraph(nodes, edges, hook_targets)


def find_call_sequences_to_target(
    cg: CallGraph, entry: CgNode, target: HookTarget
) -> list[list[CgEdge]]:
    if entry not in cg.nodes.values():
        print(f"{entry} not found in call graph")
        return []

    entry_labels = [k for k, v in cg.nodes.items() if v == entry]
    assert len(entry_labels) == 1, "found multiple entries"
    entry_label = entry_labels[0]

    edges = defaultdict(list)
    for e in cg.edges:
        edges[e.caller].append(e)

    target_labels = [k for k, v in cg.nodes.items() if v == target.node]

    paths = []

    # Each path would be represented as a list[Edge]. nodes_on_path is just used to
    # avoid finding duplicate paths.

    nodes_on_path = deque()
    edges_on_path = deque()

    def dfs(node: str) -> None:
        nodes_on_path.append(node)

        if node in target_labels:
            paths.append(list(edges_on_path))
            return

        for edge in edges[node]:
            if edge.callee not in nodes_on_path:
                edges_on_path.append(edge)

                dfs(edge.callee)

                edges_on_path.pop()

        nodes_on_path.pop()

    dfs(entry_label)

    return paths


def formulate_prompt(input_name: str, input_type: str, icfg_desc: str) -> str:
    return (
        f"Give me `{input_name}` of type `{input_type}`, such that the following"
        f" conditions are met:\n\n{icfg_desc}"
        "\n\n"
        "Your answer should be a python program that dumps the expected data to"
        " the file `input.bin`."
    )


def query_llm_and_run_response(prompt: str) -> bytes | None:
    messages = [{"content": prompt, "role": "user"}]
    key = os.getenv("LITELLM_KEY", None)
    response = completion(
            model="gpt-4-0613" if not os.getenv("LITELLM_KEY", None) else "oai-gpt-4o",
            messages=messages,
            base_url=os.getenv("AIXCC_LITELLM_HOSTNAME", None),
            extra_headers={"Authorization": f"Bearer {key}"} if key else {},
            custom_llm_provider="openai",
        )
    content = response.choices[0].message.content
    assert isinstance(content, str)

    try:
        blocks = extract_markdown_code_blocks(content)
        code = blocks[0]
    except Exception:
        return None

    with NamedTemporaryFile(buffering=0, suffix=".py") as f:
        f.write(code.encode())

        with TemporaryDirectory() as tmp_dir:
            cp = subprocess.run(
                ["python3", f.name], cwd=tmp_dir, text=True, capture_output=True
            )

            if cp.returncode != 0:
                return None

            bin_path = Path(tmp_dir, "input.bin")
            if not bin_path.is_file():
                return None

            bin = bin_path.read_bytes()

    return bin


def extract_markdown_code_blocks(content: str) -> list[str]:
    lines = content.splitlines(keepends=True)

    in_code_block = False
    start_pattern = r"\s*```\w*\s*"
    end_pattern = r"\s*```\s*"

    start, end = -1, -1
    intervals = []

    for idx, line in enumerate(lines):
        if (not in_code_block) and re.match(start_pattern, line):
            in_code_block = True
            start = idx + 1
        elif in_code_block and re.match(end_pattern, line):
            in_code_block = False
            end = idx
            intervals.append((start, end))

    res = ["".join(lines[start:end]) for start, end in intervals]
    return res


if __name__ == "__main__":
    main()
    # foo("hello world")
