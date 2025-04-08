# IDDM Data Connector Code Generator

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0) <!-- Updated Badge -->

## Description

This project provides a command-line tool written in Python to automatically generate Java-based data connectors for Radiant Logic IDDM v8.1+. These connectors bridge arbitrary RESTful APIs (described via OpenAPI) with IDDM's LDAP-centric view, adhering to the patterns and requirements of the IDDM Connector Java SDK (v8.1+).

The generator takes an OpenAPI specification and a custom JSON mapping file as input and produces a standard Maven project containing the necessary Java code, configuration metadata (`meta.json`), schema definition (`schema.orx`), and build file (`pom.xml`).

## Features

*   Parses OpenAPI v2/v3 specifications (JSON format).
*   Parses a custom JSON mapping file defining the transformation between the REST API and the desired LDAP schema.
*   Validates input OpenAPI and Mapping files against basic structural schemas.
*   Generates `meta.json` for IDDM Data Source configuration UI based on OpenAPI `servers` and `securitySchemes`.
*   Generates `schema.orx` defining LDAP object classes and attributes based on OpenAPI schemas and the mapping file.
*   Generates Java code targeting the IDDM Connector SDK v8.1+, following recommended patterns:
    *   `@CustomConnector` annotated main class.
    *   Implementation of relevant SDK Operation Interfaces (`Search`, `Insertion`, `Modification`, `Deletion`, `TestConnect`).
    *   Generation of `TypeConverter` classes for request/response translation (recommended pattern).
    *   Generation of a Backend Client class (using OkHttp) annotated with `@ManagedComponent`.
    *   Generation of Request/Response POJOs from OpenAPI schemas (using Jackson annotations).
    *   Leverages SDK Dependency Injection (`@Inject`, `@Properties`, `@ManagedComponent`).
*   Generates a standard Maven `pom.xml` file with necessary dependencies (IDDM SDK, OkHttp, Jackson, etc.).
*   Optionally attempts to build the generated connector JAR using Maven.

## Requirements

*   Python 3.8+
*   [uv](https://github.com/astral-sh/uv) (for Python package management)
*   (Optional, for building generated Java code): Apache Maven installed and configured in your system's PATH.
*   (Optional, for full schema generation features): `jsonpath-ng` (`uv pip install jsonpath-ng`)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd DataConnectorsCodeGen
    ```

2.  **Create and activate a virtual environment using `uv`:**
    ```bash
    uv venv
    source .venv/bin/activate  # Linux/macOS
    # .venv\Scripts\activate  # Windows (Command Prompt/PowerShell)
    ```

3.  **Install dependencies using `uv`:**
    ```bash
    uv pip install -r requirements.txt
    ```

## Usage

The generator is run from the command line.

```bash
python -m dataconnectors_codegen.main generate --openapi <path/to/openapi.json> --mapping <path/to/mapping.json> [OPTIONS]
```

**Required Arguments:**

*   `--openapi`, `-o`: Path to the OpenAPI specification file (JSON).
*   `--mapping`, `-m`: Path to the mapping specification file (JSON).

**Common Optional Arguments:**

*   `--output`, `-out`: Output directory for the generated connector project (default: `./generated_connector`).
*   `--package-name`, `-p`: Java package name for the generated code (default: `com.example.generated.connector`).
*   `--sdk-version`, `-sv`: Target IDDM SDK version (default: `8.1.0`). **Ensure this matches your IDDM environment.**
*   `--java-version`, `-jv`: Target Java version for compilation (default: `11`).
*   `--okhttp-version`, `-okv`: OkHttp version to use (default: `4.12.0`).
*   `--jackson-version`, `-jsv`: Jackson version to use (default: `2.17.0`).
*   `--schema-extraction`, `-se`: Enable generation of `SchemaExtractionOperations` (flag, default: false).
*   `--help`: Show the help message and exit.

**Example:**

```bash
python -m dataconnectors_codegen.main generate \
    --openapi ./specs/my_api_spec.json \
    --mapping ./specs/my_api_mapping.json \
    --output ./my-generated-connector \
    --package-name com.mycompany.iddm.connector.myapi \
    --sdk-version 8.1.1
```

After generation, you can optionally let the tool attempt to build the JAR:

```
Do you want to attempt to build the connector JAR using Maven? (Requires Maven in PATH) [y/N]: y
```

## Input File Formats

*   **OpenAPI Specification:** A standard OpenAPI v2 or v3 JSON file describing the target REST API.
*   **Mapping Specification:** A custom JSON file defining the translation logic. See `dataconnectors_codegen/parsers/mapping_parser.py` for the expected schema (`MAPPING_SCHEMA`). Basic validation is performed on load.

## Generated Project Structure

The tool generates a standard Maven project structure:

```
generated_connector/
├── pom.xml
└── src/
    └── main/
        ├── java/
        │   └── com/example/generated/connector/  (your package structure)
        │       ├── client/
        │       │   └── ...Client.java
        │       ├── converter/
        │       │   └── LdapToBackendRequestConverter.java
        │       │   └── BackendToLdapResponseConverter.java
        │       ├── model/
        │       │   ├── BackendRequest.java
        │       │   ├── BackendResponse.java
        │       │   └── ... (Generated POJOs)
        │       └── ...Connector.java (Main connector class)
        └── resources/
            ├── META-INF/
            │   └── connector/
            │       ├── meta.json
            │       └── schema.orx
            └── mapping_config.json (Copy of input mapping)
```

## Testing the Generated Connector

Testing the generated Java connector code requires significant setup outside of this generator tool:

1.  **IDDM SDK Dependencies:** The generated code needs the specific IDDM Connector SDK JARs (v8.1+) available during compilation and testing (e.g., via a Maven repository populated from an IDDM installation).
2.  **IDDM Runtime Environment:** The generated code relies on the SDK's runtime for Dependency Injection (`@Inject`, `@ManagedComponent`), Property Injection (`@Properties`), and the TypeConverter pipeline. Testing components often requires mocking these SDK interactions or running within a specialized test harness that mimics the SDK environment.
3.  **Mock Backend API:** Integration tests require a mock HTTP server that implements the REST API defined in the input OpenAPI specification.

Currently, this tool does **not** generate JUnit test skeletons, mock SDK components, or mock API server setups.

## Development

(TODO: Add instructions for setting up a development environment, running tests for the generator itself, linting, etc.)

## Contributing

(TODO: Add contribution guidelines if applicable.)

## License

This project is licensed under the Apache License, Version 2.0. See the full license text at: https://www.apache.org/licenses/LICENSE-2.0
