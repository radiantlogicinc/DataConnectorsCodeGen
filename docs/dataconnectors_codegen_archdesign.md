# Data Connectors Code Generator - High-Level Technical Design

## 1. Introduction

This document outlines the high-level technical design for the Python command-line application responsible for generating Java-based data connectors for Radiant Logic IDDM v8.1+. The goal is to automate the creation of connectors that bridge arbitrary RESTful APIs with IDDM's Ldap-centric view, adhering to the patterns and requirements of the new IDDM Connector Java SDK (v8.1+).

The primary inputs are an OpenAPI specification for the target REST API and a JSON mapping file defining the correspondence between the REST API schema and the desired Ldap schema. The generator produces a deployable Java package (JAR) containing the necessary connector logic, configuration metadata, and schema definition.

## 2. Inputs

The code generator requires the following inputs:

1.  **OpenAPI Specification:** A JSON file conforming to the OpenAPI (Swagger) standard (version 2 or 3), describing the target REST API (paths, operations, schemas, security schemes, servers).
2.  **Mapping Specification:** A JSON file detailing the mapping between REST API elements (endpoints, JSON fields) and Ldap schema elements (object classes, attributes, DN structure). This guides the translation logic, especially for request/response conversions.
3.  **(Optional) Configuration Overrides:** Command-line arguments or a configuration file to specify output locations, package names, or override certain generation parameters.

## 3. Outputs

The generator will produce a structured Java project (likely Maven-based, given the `sample_connector` structure) containing the following key artifacts, ultimately packaged into a single deployable JAR:

1.  **`meta.json`:** Defines connection parameters required by IDDM (derived from OpenAPI `servers` and `securitySchemes`). Used by IDDM to render the Data Source configuration UI.
2.  **Schema Definition (`.orx` or future format):** Defines the Ldap object classes and attributes exposed by the connector, based on the OpenAPI `schemas` and `paths`, guided by the mapping specification. This represents the full data structure available from the API.
3.  **Java Code Package:** Compiled Java classes implementing the connector logic using the IDDM Connector SDK (v8.1+). This includes:
    *   Main Connector Class (`@CustomConnector`)
    *   Operation Interface Implementations (`Search`, `Insertion`, `Modification`, `Deletion`, `TestConnect`)
    *   Type Converters (`Converter<IN, OUT>`, `@ManagedComponent`) - *Recommended Pattern*
    *   Backend Client Class (`@ManagedComponent`)
    *   Request/Response POJOs
    *   Appropriate SDK annotations (`@Inject`, `@Properties`).
4.  **Build File (`pom.xml`):** A Maven project file to manage dependencies (IDDM SDK, HTTP client libraries, etc.) and facilitate compilation and packaging.

## 4. Core Architecture (Python Application)

The Python application will be structured modularly:

1.  **Command-Line Interface (CLI):**
    *   Built using libraries like `argparse` or `click`.
    *   Accepts paths to input files (OpenAPI spec, mapping spec).
    *   Accepts output directory path and other configuration options.
    *   Provides help messages and handles command-line errors.
2.  **Input Parsers & Validators:**
    *   Modules to load and parse the OpenAPI JSON and mapping JSON files.
    *   Includes validation logic to ensure the input files conform to expected schemas and contain necessary information (e.g., valid OpenAPI structure, required mappings).
3.  **Code Generation Engine:**
    *   The central orchestrator.
    *   Takes the parsed and validated input data structures.
    *   Invokes specific generator components for each output artifact (`meta.json`, schema, Java classes, `pom.xml`).
4.  **Template Engine:**
    *   Utilizes a template engine (e.g., Jinja2) for generating files with repetitive structures, primarily:
        *   Java source code files (filling in class names, method signatures, boilerplate logic based on parsed inputs).
        *   `meta.json` file structure.
        *   Schema definition file (`.orx` XML or future format).
        *   `pom.xml` file.
    *   Templates will encapsulate the standard structure of SDK components (Connector class, Converters, Client).
5.  **Java Artifact Builder/Packager:**
    *   Orchestrates the final steps:
        *   Places generated source files (`.java`, `meta.json`, `.orx`, `pom.xml`) into a standard Maven project directory structure.
        *   **(Option 1 - Invoke Maven):** Executes Maven (`mvn package`) via `subprocess` to compile the Java code and package the JAR. Requires Maven to be installed on the system running the generator.
        *   **(Option 2 - Direct Compilation/Packaging):** Use `subprocess` to call `javac` directly for compilation and `jar` for packaging. Requires managing classpath and dependencies manually, which is more complex. (Maven is preferred).

## 5. Key Generation Logic Details

The core logic resides in transforming the input specifications into the output artifacts:

1.  **`meta.json` Generation:**
    *   Extract server URLs from the OpenAPI `servers` block.
    *   Extract authentication requirements from OpenAPI `securitySchemes` (API Keys, OAuth, Basic Auth, etc.).
    *   Map these to the `meta.json` property structure (`name`, `label`, `type`, `required`, etc.).
2.  **Schema Generation (`.orx` / Future Format):**
    *   Analyze OpenAPI `paths` and `components.schemas` to identify potential backend entities and their attributes.
    *   Use the mapping specification to determine:
        *   Ldap `objectclass` names (e.g., `KcUsers`).
        *   Mapping between object classes and corresponding REST resources/paths.
        *   Ldap attribute names and their mapping to JSON fields in API responses.
        *   Identification of primary key attributes.
    *   Generate the schema file exposing the *full* structure defined in the API spec, mapped according to the mapping file.
3.  **Java Code Generation (SDK v8.1+):**
    *   **Main Connector Class:** Generate a class annotated with `@CustomConnector(metaJson = "meta.json")`.
    *   **Operation Interfaces:** Determine which interfaces (`Search`, `Insertion`, etc.) to implement based on the HTTP methods present in the OpenAPI `paths` (e.g., GET -> `Search`, POST -> `Insertion`, PUT/PATCH -> `Modification`, DELETE -> `Deletion`). Always include `TestConnect`.
    *   **Type Converters (Recommended):**
        *   Generate request converter (`Converter<LdapRequest, BackendRequest>`) annotated with `@ManagedComponent`. This involves the complex logic of translating `LdapRequest` (scope, filter, attributes) into specific REST API calls (paths, query parameters, request bodies) based on the OpenAPI spec and the mapping file. Filters might require complex translation to API query parameters.
        *   Generate response converter (`Converter<BackendResponse, ResponseEntity>` or `SearchResultEntry`) annotated with `@ManagedComponent`. This translates REST responses (JSON bodies) into IDDM's expected Ldap representation, using the mapping file.
        *   Generate corresponding `BackendRequest` and `BackendResponse` POJOs based on OpenAPI schemas and operation parameters/responses.
    *   **Backend Client:** Generate a class annotated with `@ManagedComponent` to handle HTTP communication (using a library like OkHttp, Apache HttpClient, or `java.net.http.HttpClient`). It will manage authentication based on `meta.json` properties injected via `@Inject` and `@Properties`. Methods will accept `BackendRequest` POJOs and return `BackendResponse` POJOs.
    *   **Dependency Injection:** Use `@Inject` for injecting dependencies (like Converters, Client, Properties) into constructors. Use `@Properties` to inject configuration sets (e.g., `CONNECTION_CONFIGURATION`, `SCHEMA`).
    *   **Operation Logic:**
        *   If using converters, the main connector methods become simple orchestrators calling the client and relying on the SDK pipeline for conversion.
        *   If *not* using converters (simpler, less modular approach), the main connector methods contain all translation logic directly.
    *   **`TestConnect` Implementation:** Generate a basic `testConnect` method in the main connector class that uses the Backend Client to make a simple API call (e.g., accessing the root endpoint or a specific metadata endpoint) to validate credentials and connectivity.
4.  **`pom.xml` Generation:**
    *   Generate a `pom.xml` including dependencies for:
        *   The IDDM Connector SDK (version corresponding to v8.1+).
        *   An HTTP client library.
        *   JSON processing library (e.g., Jackson).
        *   Build plugins (e.g., Maven compiler plugin, JAR plugin).

## 6. Technology Stack (Python)

*   **Python Version:** 3.8+
*   **Core Libraries:**
    *   `json`: For parsing input files.
    *   `argparse` / `click`: For CLI.
    *   `Jinja2`: For templating source files and configurations.
    *   `subprocess`: For potentially invoking `mvn`, `javac`, `jar`.
*   **(Optional) Schema Validation:** Libraries like `jsonschema` for validating input JSONs.

## 7. High-Level Workflow

1.  User invokes the Python script via CLI, providing paths to OpenAPI spec, mapping spec, and output directory.
2.  CLI parser validates arguments.
3.  Input Parser loads and validates OpenAPI and mapping JSON files.
4.  Code Generation Engine analyzes inputs.
5.  Template Engine generates Java source files, `meta.json`, schema file, and `pom.xml` using parsed data and pre-defined templates.
6.  Generated files are written to the output directory in a Maven project structure.
7.  Java Artifact Builder invokes Maven (`mvn package`) to compile Java code and package the final connector JAR.
8.  The final JAR is placed in the specified output location (e.g., `target/` within the generated project).

## 8. Error Handling & Validation

*   Implement strict validation for input OpenAPI and mapping JSON files against their expected schemas.
*   Provide clear error messages if required information is missing or malformed in inputs.
*   Handle potential errors during file generation and the build process (e.g., Maven errors).
*   Log progress and errors effectively.

## 9. Note on `sample_connector`

This design document outlines an approach targeting the latest IDDM Connector SDK (v8.1+) guidelines, strongly recommending the use of Type Converters for modularity, as detailed in the provided lecture notes and design documents.

The specific Java code within the provided `sample_connector` directory was not reviewed as part of this design preparation. It's possible the sample implements an older pattern, doesn't utilize Type Converters, or deviates in other ways from the recommendations outlined here. The generator described in this document aims to produce code conforming to the *latest documented best practices* for the v8.1+ SDK.

## 10. Future Considerations

*   **Advanced OpenAPI Features:** Handling more complex OpenAPI features like `oneOf`, `anyOf`, polymorphic schemas, callbacks, links.
*   **Schema Format Evolution:** Adapting to potential changes in IDDM's preferred schema definition format (if `.orx` is replaced).
*   **Enhanced Robustness:** Generating more sophisticated error handling, retry logic, or basic rate-limiting awareness in the Backend Client based on OpenAPI hints (e.g., `x-ratelimit` extensions).
*   **Mapping UI/Tool:** A separate tool or UI could potentially assist users in creating the mapping JSON file.
*   **Test Generation:** Generating basic unit test skeletons for converters or the client.
