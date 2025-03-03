# CRS

## Description

This is the CRS (Cyber Reasoning System) submitted by team "Healing Touch" to the DARPA AIxCC semi-final competition in 2024.

## Setup and Installation

The following section includes steps for running the CRS *locally* outside of Kubernetes using docker compose.

1. Clone the repository:

```bash
git clone https://github.com/DARPA-AIxCC/asc-crs-healing-touch
```

2. Create the environment file:
   - Create `sandbox/env` file containing the required API keys for AI tools
   - Reference the [example.env](https://github.com/DARPA-AIxCC/asc-crs-healing-touch/blob/main/sandbox/example.env) for the required format

3. Update the `cp_root.yaml` with your target subject
   - For example, using the public NGINX: https://github.com/aixcc-public/challenge-004-nginx-cp

4. Build and start the environment:
```bash
make build
make up
make crs-shell  # This enters the main container
```

## Running Workflows

Once inside the container (`make crs-shell`), navigate to the `/app/orchestrator` directory. Execute workflows using:

```bash
timeout -k 5m 4h python3 -m main -c /crs_scratch/benchmark/darpa/nginx/workflow-1-30918.json --special-meta=/crs_scratch/benchmark/darpa/nginx/meta-data.json
```

### Understanding Configuration Files

The system uses two main configuration files:

1. **Workflow JSON**: Controls the execution flow and tool configurations
   - Enable/disable specific tools (fuzz, crash-analyze, bisect, etc.)
   - Configure container resources (CPU, memory)
   - Set timeouts and test limits
   - Define task profiles and execution parameters
   - Example file: 

<details>
   <summary>Composite workflow example</summary>


```json
{
    "general": {
        "parallel": false,
        "enable_ui": false,
        "secure-hash": false,
        "debug-mode": true,
        "cpus": 6
    },
    "tasks": {
        "default": {
            "compact-results": true,
            "dump-patches": false,
            "only-analyse": false,
            "only-setup": false,
            "only-instrument": false,
            "only-test": false,
            "rebuild-all": false,
            "rebuild-base": false,
            "use-cache": false,
            "use-subject-as-base": true,
            "use-container": true,
            "use-gpu": false,
            "use-purge": false,
            "container-profiles-id-list": [
                "CP1"
            ],
            "task-profiles-id-list": [
                "TP1"
            ]
        },
        "chunks": [
            {
                "type": "composite",
                "composite-sequence": {
                    "fuzz": [
                        {
                            "name": "libfuzzerfuzz",
                            "local": true,
                            "ignore": false
                        },
                        {
                            "name": "klee",
                            "local": true,
                            "ignore": true
                        },
                        {
                            "name": "aflsmarter",
                            "local": true,
                            "ignore": false
                        },
                        {
                            "name": "dumbfuzzer",
                            "local": true,
                            "ignore": false
                        }
                    ],
                    "crash-analyze": [
                        {
                            "name": "sanitizeparser",
                            "local": true,
                            "ignore": false,
                            "type": "analyze"
                        }
                    ],
                    "bisect": [
                        {
                            "name": "chopper",
                            "local": true,
                            "ignore": false,
                            "type": "analyze"
                        }
                    ],
                    "localize": [
                        {
                            "name": "e9patchneosbfl",
                            "local": true,
                            "ignore": false
                        }
                    ],
                    "repair": [
                        {
                            "name": "SOME_LLM_AGENT",
                            "local": true,
                            "ignore": false
                        },
                        {
                            "name": "hermes",
                            "local": true,
                            "ignore": false
                        },
                        {
                            "name": "ddrepair",
                            "local": true,
                            "ignore": false
                        }
                    ],
                    "validate": [
                        {
                            "name": "valkyrie",
                            "local": true,
                            "ignore": false
                        }
                    ],
                    "iterative-repair": [
                        {
                            "name": "iterativehermes",
                            "local": true,
                            "ignore": false,
                            "type": "repair"
                        }
                    ]
                },
                "benchmarks": [
                    {
                        "name": "darpa",
                        "bug-id-list": [
                            "*"
                        ]
                    }
                ],
                "tools": [
                    {
                        "name": "basicworkflow",
                        "params": "",
                        "local": true
                    }
                ]
            }
        ]
    },
    "profiles": {
        "container-profiles": [
            {
                "id": "CP1",
                "cpu-count": 6,
                "mem-limit": "16g",
                "enable-network": true
            }
        ],
        "task-profiles": [
            {
                "id": "TP1",
                "timeout": 4,
                "fault-location": "auto",
                "passing-test-ratio": 1,
                "passing-test-limit": 30,
                "failing-test-limit": 30,
                "fuzz-timeout": 4,
                "localize-timeout": 0.5,
                "repair-timeout": 1
            }
        ]
    }
} 
```
</details>

2. **Meta-data JSON**: Defines the target subject configuration
   - Specifies test harnesses and their locations
   - Defines source locations and build scripts
   - Configures test inputs and analysis outputs
   - Sets up sanitizer configurations
   - Specifies base images and container settings
   - Example file: https://github.com/DARPA-AIxCC/asc-crs-healing-touch/blob/main/crs/src/orchestrator/benchmark/darpa/meta-data.json

The workflow can be customized by:
- Toggling tools using the `ignore` flag in the workflow JSON
- Adjusting resource allocation in container profiles
- Modifying timeouts and test limits in task profiles
- Updating source paths and build configurations in meta-data
- Configuring different test harnesses or build scripts through meta-data

# AIxCC Competition Infrastructure and Information

## CRS Constraints on Docker and Virtualization

In the competition environment, a CRS is expected to use Docker (via `run.sh`)
to exercise the CPs that are packaged and configured to be built, tested, and
patched using the provided Docker container.

One CP (the public Linux kernel CP) includes `virtme-ng` in its CP-specific
Docker container for the purposes of testing the built kernel.

This is the only form of nested virtualization or nested containerization that
will be supported by the competition environment. A CRS **MUST NOT** assume that
nested containers or another virtualization/hypervisor technology will be
compatible with the competition environment.

## Environment Variables & GitHub Secrets

Each competitor CRS repository will come pre-packaged with a list of GitHub secrets and environment
variables. Teams may change the values of these secrets (e.g. to their own collaborator API keys);
however, teams must not change the variable names. Also, teams must ensure their services use the
core variables related to the iAPI and LiteLLM connections.

For local development and during Phase 1 of the Evaluation Window, competitors are expected to
use / provide their own keys and secrets. During subsequent phases of the evaluation window
and at competition, the AIxCC infrastructure team will override these values with their own.

There are currently 5 LLM Provider environment variables declared but not populated in example.env, which will be populated at competition time:

- OPENAI\_API\_KEY
- AZURE\_API\_KEY
- AZURE\_API\_BASE
- GOOGLE_APPLICATION_CREDENTIAL
- ANTHROPIC\_API\_KEY

Note: For local development, the [./sandbox/example.env](./sandbox/example.env) file should be
copied to `./sandbox/env`. This file is included in the `.gitignore` so competitors don't
accidentally push it to their repository.

*TBD* - These variables and the LiteLLM configuration file are not yet complete. This will be released in a CRS sandbox update.
We will continue iterating on the CRS sandbox as we grow closer to the competition in order to support newer versions of components.

Please see the competition rules and technical release as the cut off dates for changes will be described there.

## LiteLLM Models Supported

| Provider  | Model                  | Pinned Version              | Requests per Minute (RPM) | Tokens per Minute (TPM)  |
| --------- | ---------------------- | --------------------------- | --------------------------| -------------------------|
| OpenAI    | gpt-3.5-turbo          | gpt-3.5-turbo-0125          | 800                       | 80,000                   |
| OpenAI    | gpt-4                  | gpt-4-0613                  | 200                       | 20,000                   |
| OpenAI    | gpt-4-turbo            | gpt-4-turbo-2024-04-09      | 400                       | 60,000                   |
| OpenAI    | gpt-4o                 | gpt-4o-2024-05-13           | 400                       | 300,000                  |
| OpenAI    | text-embedding-3-large | text-embedding-3-large      | 500                       | 200,000                  |
| OpenAI    | text-embedding-3-small | text-embedding-3-small      | 500                       | 200,000                  |
| Anthropic | claude-3-sonnet        | claude-3-sonnet-20240229    | 1,000                     | 80,000                   |
| Anthropic | claude-3-opus          | claude-3-opus-20240229      | 1,000                     | 40,000                   |
| Anthropic | claude-3-haiku         | claude-3-haiku-20240307     | 1,000                     | 100,000                  |
| Google    | gemini-pro             | gemini-1.0-pro-002          | 120                       | pending (as of 20240610) |
| Google    | gemini-1.5-pro         | gemini-1.5-pro-preview-0514 | 120                       | pending (as of 20240610) |
| Google    | textembedding-gecko*   | textembedding-gecko@003*    | pending (as of 20240610)  | pending (as of 20240610) |

Note: OpenAI Embedding models have not currently been released in more than a single version, thus pinned/name strings are identical.

All OpenAI models will also be matched by an Azure-hosted version. Competitors will be able to freely request the
model they like by the Model name in chart above, plus a prefix "oai-" or "azure-".
Ex. "oai-gpt-4o".
This was done because of performance differences between the models as hosted on OAI vs Azure infrastructure. The models themselves are guaranteed to be identical but no such promises can be made as regards supporting provider infrastrcture.

Note: OAI Embedding models have not currently been released in more than a single version.

These are utilized by hitting the LiteLLM /chat/completions endpoint, specifying model and message using the OpenAI JSON request format.
Note: Further models will be supported in subsequent iterations.

The Requests per Minute (RPM) and Tokens per Minute (TPM) columns in the table above are
rate limits that are enforced per CRS for the ASC. The LiteLLM proxy will be responsible for
implementing these limits. The RPM and TPM limits are enforced per model, not in aggregate across
models or providers.

Note: the "\*" next to model "textembedding-gecko" indicates this model target is still in flux.
The AIxCC infrastructure team is still waiting on LiteLLM to finalize support for the model
"text-embedding-04". If this newer model is not integrated in time to support its use during the
ASC, then the fallback will likely be "textembedding-gecko@003".

## Local Development

We recommend using Ubuntu 22.04 LTS for CRS Sandbox development and will be unable to investigate issues with other base operating systems.

### Precommit

This repository has a [.pre-commit-config.yaml](.pre-commit-config.yaml) file for assisting with local development.

While competitors are not required to use this, they may find it easier to pass the mandatory evaluation checks.

You can install the command-line tool by going [here](https://pre-commit.com/#install)

### Dependencies

Most dependencies in this repository can be automatically managed by `mise`, but you'll have to install the following yourself:

- docker >= 24.0.5
- docker-compose >= 2.26.1
- GNU make >= 4.3
- kind >= 0.23.0 (for running local kubernetes clusters in docker)

Additionally, you will need permissions to interact with the Docker daemon.  Typically this means adding your user to the `docker` group.

### Working with Docker-in-Docker

The `crs-sandbox` contains its own Docker daemon inside of a Docker container.
By default this is not accessible on the host machine, but you can enable the
port mapping by editing
[`./compose_local_overrides.yaml`](./compose_local_overrides.yaml).  Note that
by doing this, you are exposing the Docker daemon on your host without
authentication enabled.

Once you've done that, set `DOCKER_HOST=tcp://127.0.0.1:2375`.

```bash
export DOCKER_HOST=tcp://127.0.0.1:2375
docker logs <container name>
```

#### Dependencies managed using mise

This repository defines its dependencies in a [`.tool-versions`](./.tool-versions) file.
[`mise`](https://mise.jdx.dev/getting-started.html#quickstart) can read this file and automatically install the tools at the required versions.
Install `mise`, set it up in your shell, and then run `mise install`.
`mise` will then manage your `PATH` variable to make the tools available whenever you `cd` into this repository.

We've included a Makefile with helpful targets to make working with the CRS Sandbox easier.
However, you can copy any commands and run them on your own.
Please note the use of `--profile` with all `docker compose` commands.
This is so we can easily swap `--profile development` with `--profile competition` at competition time, but competitors can use the `--profile development` to run the local copy of emulated resources.

### Data Sharing & Volumes

A CRS will find the CPs under evaluation in the volume indicated by the environment variable
`${AIXCC_CP_ROOT}`. At competition time and likely during some part of the evaluation
window, this volume will be configured as read-only. As such, a CRS **MUST** copy a CP
from `${AIXCC_CP_ROOT}` to a writable location in order to build or test it.

The volume indicated by the environment variable `${AIXCC_CRS_SCRATCH_SPACE}` will be writable
by the CRS and CPs. Moreover, this volume can be shared among the CRS services as a
shared file system. It is the responsibility of the CRS developers to ensure that
use of this shared volume is coordinated between its services to prevent data corruption
via collisions or race conditions. No other folders or volumes will be shared between
containers for competitor use during competition.

### No internet Access

As stated previously, a CRS will NOT have internet access except for via the LiteLLM proxy to the configured LLM providers.

Because of this competitors MUST provide all artifacts within their Docker container images.

All images needed to execute a CRS MUST be included under `.github/workflows/package.yml` under the `jobs.build-and-push-image.strategy.matrix.include` section.

The Game Architecture team will migrate these images to the competition environment prior to starting your CRS.

### Release Process

We've modified our original guidance on the tagging process.

All teams should be using [SemVer 2.0.0](https://semver.org/) to tag releases.

A team MUST have a tag of `v1.0.0` OR greater within their private CRS repository at competition.

Teams MUST use a `v` prefix in their tags.

All releases MUST be from the `main` branch ONLY. Failure to create release tags from `main` will lead to a failed release.

Teams can create these tags by following the GitHub Release process with <https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository>

This will automatically tag any Docker images you've specified under `.github/workflows/package.yml` outlined above.

This will also tag the Helm chart of your CRS automatically.

At competition the AIxCC Game Architecture team will use the latest SemVer tag available on your repository that was present at the end of the submission window.

### Using Make

A Makefile has been provided with a number of a commands to make it easy to clone the exemplar repos, stand up the environment, and a variety of other actions.

Copy `sandbox/example.env` to `sandbox/env` and replace the variables with your own for local development.

**If you do not have working GitHub credentials that can pull images from GHCR, `make up` will fail.**

```bash
cp sandbox/example.env sandbox/env
```

`make cps` - clones the exemplar challenges into local `./cp_root` folder (the source folder for `${AIXCC_CP_ROOT}`)
`make up` - brings up the development CRS Sandbox, you can visit <http://127.0.0.1:8080/docs> to see the iAPI OpenAPI spec.
`make down` - tears down the development CRS Sandbox

See [Makefile](./Makefile) for more commands

`make force-reset` - performs a full Docker system prune of all local docker containers, images, networks, and volumes. This can be useful if you accidentally orphaned some docker process or other resources.

### Kubernetes

The Makefile includes endpoints for `make k8s` and `make k8s/competition` which will generate a helm chart in a `./charts/` folder.
The `make k8s` command uses Kind to run Kubernetes locally and will also apply the generated Helm chart onto your cluster.
This process uses a component called [Kompose](https://kompose.io/conversion/) for translating the Docker Compose file into resources.
The CRS Sandbox will include a CI/CD action which the private repos must also use.
This will generate and push the container images to the respective per-competitor private GitHub.
This will also push the Helm chart as an OCI compliant chart to the private GitHub repos.
The `evaluator.yml` action runs `make k8s` in every pull request to `main`.
This is to ensure all resources can be properly translated into a Helm chart and deployed into Kubernetes.

#### Autoscaling

One of Kubernetes' most useful features is autoscaling.  Kompose exposes horizontal pod autoscaling, among many other
features, via labels set on services.  This example produces an HPA configuration that will scale from 3 replicas up to
12, adding and removing replicas to target an average CPU utilization of 80% and memory utilization of 1024 megabytes.
Please note these are probably not good default values for your application and you should customize them.

```yaml
services:
  job-runner:
    labels:
      # Thresholds for automatic scale up
      kompose.hpa.cpu: 80 # percentage
      kompose.hpa.memory: 1024Mi
      # High & low limits for number of replicas
      kompose.hpa.replicas.max: 12
      kompose.hpa.replicas.min: 3
```

### Architecture Diagram

This diagram depicts the CRS Sandbox during the `development` phase with `--profile development` and during the `competition` phase with `--profile competition`.
As you can see the iAPI remains as part of the CRS Sanbox but can communicate with the upstream API.
However, the LiteLLM component moves to a centralized component that does NOT run within the CRS Sandbox at competition.

![arch diagram](./.static/architecture.png)
