# Data Connectors Code Generator Project Requirements
## Connecting Arbitrary REST Endpoints to IDDM v8.1+

We are working on a code generation application that will write Java code for data connectors. These connectors facilitate data transfer between arbitrary RESTful endpoints and Radiant Logic IDDM, specifically targeting the **new IDDM Connector SDK (v8.1+)**.

IDDM acts as an integration platform, providing a unified LDAP interface over heterogeneous identity directories and APIs. The generated connectors will bridge the gap between IDDM's LDAP-centric view and the target REST API.

## Requirements

### 1. Target Platform & Input

*   The code generator will be a Python command-line application. BUT... note that the generated code will be in Java.
*   The primary inputs will be
    *   the target **REST API specification** provided as a file in **OpenAPI (Swagger) JSON format** and
    *   the mapping specifications between the target REST API and the IDDM LDAP schema, going both ways. This will also be in **JSON format**.
*   The generated code **must** target the **new RadiantLogic IDDM Connector Java SDK (v8.1+)** and its specific interfaces, annotations, and patterns.

### 2. Generated Artifacts

#### 1. Generated Artifacts - List
The code generator must produce the following artifacts, typically packaged into a deployable JAR:

1.  **`meta.json` File:** Defines the connection parameters required by the connector (e.g., API base URL, authentication details like API keys, OAuth info). This file drives the configuration UI in IDDM when creating a Data Source instance. The generator should derive these properties from the input API specification (servers, security schemes).
2.  **Schema Definition File (`.orx` or future replacement):** Defines the data structure (object classes and attributes) exposed by the REST API, mapped to Ldap concepts.
    *   This acts as the "menu" for IDDM administrators when configuring Views.
    *   The generator should derive this schema from the API specification's paths and schemas, aiming to represent the *full* available data structure.
    *   It defines Ldap object class names (e.g., `KcUsers`), maps them to backend entities, lists attributes, and identifies primary keys.
3.  **Java Code Package:** Contains the compiled Java classes implementing the connector logic using the IDDM Connector SDK.

#### 2. Generated Artifacts - Java Code Structure & SDK Usage

The generated Java code should follow the patterns encouraged by the new SDK:

*   **Main Connector Class:**
    *   Annotated with `@CustomConnector(metaJson = "...")`.
    *   Implements relevant SDK **Operation Interfaces** (e.g., `Search`, `Insertion`, `Modification`, `Deletion`, `TestConnect`) based on the available REST API methods (GET, POST, PUT/PATCH, DELETE).
    *   Uses Java Generics (`<REQ, RESP>`) on implemented interfaces, potentially using backend-specific types if Type Converters are employed.
*   **Type Converters (Recommended Pattern):**
    *   Generate separate classes implementing `Converter<IN, OUT>` and annotated with `@ManagedComponent`.
    *   **Request Converter:** Translates `LdapRequest` objects (containing scope, filter, attributes) into backend-specific request objects (e.g., `RestRequest` POJOs). This involves mapping Ldap semantics to REST API parameters, paths, and bodies. May need to handle Ldap operations requiring multiple API calls (e.g., via a `CompoundRequest` containing `SimpleRequest`s).
    *   **Response Converter:** Translates backend responses (e.g., `RestResponse` POJOs containing JSON) into `ResponseEntity` or `SearchResultEntry` objects expected by IDDM.
    *   *Note:* While recommended for separation of concerns, generating code that puts all logic directly into the main connector methods (taking `LdapRequest` and returning `LdapResponse`) is also acceptable.
*   **Backend Client Class:**
    *   Handles direct communication with the REST API (e.g., using an HTTP client library).
    *   Manages authentication (fetching/using tokens, API keys).
    *   Executes requests based on the `RestRequest` POJOs.
    *   Annotated with `@ManagedComponent` for dependency injection.
*   **Request/Response POJOs:** Simple Java classes representing the structure of requests to and responses from the target REST API.
*   **SDK Annotations:** Utilize `@Inject` and `@Properties` for dependency injection of components and configuration values (like connection details from `meta.json` or schema info needed during conversion).

#### 3. Generated Artifacts - Core Functionality Of Generated Code

*   **Operation Translation:** Implement the logic to translate IDDM Ldap operations into corresponding REST API calls:
    *   `Search` (Ldap) -> GET (REST)
    *   `Add` (Ldap) -> POST (REST)
    *   `Modify` (Ldap) -> PUT/PATCH (REST)
    *   `Delete` (Ldap) -> DELETE (REST)
*   **Parameter Mapping:** Translate Ldap request details (filter, requested attributes, scope, base DN) into appropriate REST request components (URL paths, query parameters, request bodies, headers).
*   **Response Mapping:** Translate REST responses (status codes, JSON bodies) back into Ldap result codes and `ResponseEntity`/`SearchResultEntry` objects.
*   **Connection Testing:** Implement the `TestConnect` operation to validate connectivity and authentication using the configured parameters from `meta.json`.
*   **Schema Exposure:** Provide the comprehensive schema definition (`.orx`) based on the API spec.

#### 4. Generated Artifacts - Non-Functional Considerations & Robustness

*   **Error Handling:** Implement robust error handling for API communication failures, unexpected response codes, and malformed responses from the backend.
*   **Backend Quirks:** The generated code should be reasonably resilient to potential backend issues like slightly incorrect specs or non-standard API behavior (though perfect handling of all quirks is impossible). Consider adding basic input/output validation/sanitization where appropriate.
*   **Rate Limiting:** Include (potentially via reusable boilerplate components) mechanisms to handle REST API rate limiting by respecting headers and implementing backoff/throttling strategies.
*   **N+1 Problem Mitigation:** Identify potential N+1 scenarios (where fetching details requires extra calls per item) based on the API spec. While full resolution might be complex, the generator could potentially flag these or implement basic mitigation if feasible.



