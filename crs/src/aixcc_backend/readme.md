# AIxCC Backend

Provides several tools and backend components for the AIxCC challenge.

## Tool: `aixcc-reader`

Reads AIxCC `project.yaml` descriptions and instantiates a provided template file using the input, i.e. to generate
file for the Cerberus framework. A default config file can be provided to initialise default values.

Usage:
```bash
aixcc-reader /path/to/directory/containing/project-yaml/ \
  --template-path /path-to-template/cerberus.template \
  --default-config /path-to-defaults-config/defaults.ini/.toml/.json
```

Example in `crates/metadata_extraction/tests/templating` contains an example.

Change(/disable) logging via `RUST_LOG`.

## Tool: `iapi_client`

Communicates with the iAPI server to submit different queries:

```shell
iAPI CLI tool to communicate with the iAPI web services

Usage: iapi_client <COMMAND>

Commands:
  health                         Checks the health of the iAPI service
  submit-vulnerability           Submit discovered vulnerability
  submit-generated-patch         Submit generated patch for previously submitted discovered vulnerability
  check-vulnerability-status     Checks status of given vulnerability
  check-patch-acceptance-status  Checks status of given patch
  help                           Print this message or the help of the given subcommand(s)

Options:
  -h, --help  Print help
```

The server address used is set via `AIXCC_API_HOSTNAME` and defaults to `localhost:8080`.


## Tool: `iapi_mock_server`

Provides a server implementation that mocks the AIxCC's iAPI implementation.
If started, listens on `localhost:8080`.

Passes all `iapi_function_tests.sh` tests. 