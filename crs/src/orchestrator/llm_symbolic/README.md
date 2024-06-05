# Java Input Generation

This is to generate prompts for LLM to generate inputs that trigger sanitizers.

## Setup

First, build the call graph generator:

```
cd call-graph-generator
mvn package
```

Then install python packages:

```
pip install -r requirements.txt
```

Finally, build joern:

```
echo "deb https://repo.scala-sbt.org/scalasbt/debian all main" | sudo tee /etc/apt/sources.list.d/sbt.list
echo "deb https://repo.scala-sbt.org/scalasbt/debian /" | sudo tee /etc/apt/sources.list.d/sbt_old.list
curl -sL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x2EE0EA64E40A89B84B2DF73499E82A75642AC823" | sudo apt-key add
sudo apt-get update
sudo apt-get install sbt

git clone https://github.com/joernio/joern.git
cd joern
sbt stage
```

## Usage

```
> python3 -m tss.aicc.main --help
Usage: python -m tss.aicc.main [OPTIONS]

Options:
  -l, --source-list-file PATH  file that lists source files to analyze, one
                               per line  [required]
  -d, --output-dir PATH        [required]
  -s, --santizer          [required]
  -c, --harness-class   [required]
  --help                       Show this message and exit.

```

For example, for challenge-002-jenkins-cp, put the following in `sources.txt`:

```
challenge-002-jenkins-cp/container_scripts/PipelineCommandUtilPovRunner.java
challenge-002-jenkins-cp/src/easy-test/src/test/java/PipelineCommandUtilFuzzer.java
challenge-002-jenkins-cp/src/plugins/pipeline-util-plugin/src/main/java/io/jenkins/plugins/UtilPlug/UtilMain.java
```

Then

```
python3 -m tss.aicc.main -l sources.txt -s OsCommandInjection -d output
```

Prompts would be generated at `output/prompts.json`.

## Implementation Notes

The input generation works as follows:

- in Jenkins and its plugins, find all method calls that are hooked by sanitizers (sanitizers can be found in the
docker image provided). In the Jenkins example we have, the hooked method call is  ProcessBuilder::start
found in UtilMain.java.
- in the interprocedural control flow graph (ICFG), find paths leading from the fuzzing harness to the hooked methods
in each ICFG path, collect all predicates (i.e., if conditions). Do a slicing on each predicate to collect the statements
they depend on.
- present the predicates and slices to an LLM.

The dependencies involved in implementation are:

- Spoon (https://spoon.gforge.inria.fr/) - for building call graph (as a step in building ICFG)
- python binding of treesitter (https://github.com/tree-sitter/py-tree-sitter) - for building AST (as a step in building ICFG) and collecting predicates.
- Joern (https://docs.joern.io/) - for slicing.

Several considerations in implementation:
- The ICFG is built on source code instead of Java bytecode. Although an analysis on bytecode would be more accurate,
    it is less robust, because it's difficult to find out the full classpath in the challenge project without manually investigating the build scripts.
    Source code analysis can still partially work when some files are missing.
- For building call graph, Spoon is more convenient than treesitter, because it does some additional inference, e.g., inferring parameter
    types from the actual argument types. For building AST, treesitter was chosen over Spoon, so that things can be done in Python rather than
    Java.
- A problem with Joern is its sometimes-huge memory usage.


