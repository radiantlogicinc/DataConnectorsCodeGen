import os
import re
from typing import Dict, Any, List, Set, Callable, Optional
import logging
import json # Add json import for metadata serialization

# Ensure absolute imports are used
from parsers.openapi_parser import OpenAPISpec
from parsers.mapping_parser import MappingSpec
from generator.meta_generator import _to_camel_case # Reuse helper

log = logging.getLogger(__name__)

# --- Java SDK Constants ---
# TODO: Refine these based on actual SDK class names/packages
SDK_PACKAGE = "com.radiantlogic.iddm.connector.sdk"
CUSTOM_CONNECTOR_ANNOTATION = f"{SDK_PACKAGE}.annotation.CustomConnector"
MANAGED_COMPONENT_ANNOTATION = f"{SDK_PACKAGE}.annotation.ManagedComponent"
INJECT_ANNOTATION = f"{SDK_PACKAGE}.annotation.Inject"
PROPERTIES_ANNOTATION = f"{SDK_PACKAGE}.annotation.Properties"
INJECTABLE_PROPS_ENUM = f"{SDK_PACKAGE}.core.InjectableProperties" # Assumed enum name

READ_OPERATIONS_INTERFACE = f"{SDK_PACKAGE}.op.ReadOperations"
CREATE_OPERATIONS_INTERFACE = f"{SDK_PACKAGE}.op.CreateOperations"
MODIFY_OPERATIONS_INTERFACE = f"{SDK_PACKAGE}.op.ModifyOperations"
DELETE_OPERATIONS_INTERFACE = f"{SDK_PACKAGE}.op.DeleteOperations"
TEST_CONNECT_OPERATIONS_INTERFACE = f"{SDK_PACKAGE}.op.TestConnectionOperations" # Assuming interface name
SCHEMA_EXTRACTION_OPERATIONS_INTERFACE = f"{SDK_PACKAGE}.op.SchemaExtractionOperations" # Assuming interface name

LDAP_REQUEST_CLASS = f"{SDK_PACKAGE}.request.LdapRequest"
SEARCH_REQUEST_CLASS = f"{SDK_PACKAGE}.request.SearchRequest"
ADD_REQUEST_CLASS = f"{SDK_PACKAGE}.request.AddRequest"
MODIFY_REQUEST_CLASS = f"{SDK_PACKAGE}.request.ModifyRequest"
DELETE_REQUEST_CLASS = f"{SDK_PACKAGE}.request.DeleteRequest"

RESPONSE_ENTITY_CLASS = f"{SDK_PACKAGE}.response.ResponseEntity"
SEARCH_RESULT_ENTRY_CLASS = f"{SDK_PACKAGE}.response.SearchResultEntry"
RESPONSE_STATUS_ENUM = f"{SDK_PACKAGE}.response.ResponseStatus"

CONVERTER_INTERFACE = f"{SDK_PACKAGE}.converter.TypeConverter"

# Assumed names for generated backend request/response base types
BACKEND_REQUEST_BASE = "BackendRequest"
BACKEND_RESPONSE_BASE = "BackendResponse"
# --- End Java SDK Constants ---

# --- Java Generation Utilities ---

# BASIC_ATTRIBUTES_CLASS = "javax.naming.directory.BasicAttributes"

# Jackson Annotations (Assuming Jackson is the chosen library)
JACKSON_JSON_PROPERTY_ANNOTATION = "com.fasterxml.jackson.annotation.JsonProperty"

def to_java_class_name(name: str) -> str:
    """Converts a name (e.g., from OpenAPI schema) to a Java ClassName."""
    if not name:
        return "UnnamedModel"
    # Remove invalid characters, replace separators with spaces
    name = re.sub(r'[^a-zA-Z0-9_\s-]+', '', name)
    name = re.sub(r'[_\s-]+', ' ', name).strip()
    # Capitalize words and join
    return "".join(word.capitalize() for word in name.split())

def to_java_variable_name(name: str) -> str:
    """Converts a name to a Java variableName (camelCase)."""
    class_name = to_java_class_name(name)
    if not class_name:
        return "unnamedVar"
    return class_name[0].lower() + class_name[1:]

def get_java_type(schema_prop: Dict[str, Any], model_package: Optional[str] = None, imports: Optional[Set[str]] = None) -> str:
    """Maps OpenAPI property type to Java type name (simple name),
       adding necessary fully qualified imports to the passed set.
    """
    # Ensure imports set exists if provided
    if imports is None:
        imports = set() # Work locally if no set provided, though caller should provide one

    openapi_type = schema_prop.get('type', 'object')
    openapi_format = schema_prop.get('format')
    java_type = "Object" # Default fallback

    if openapi_type == 'string':
        if openapi_format == 'date':
            imports.add("java.time.LocalDate")
            java_type = "LocalDate"
        elif openapi_format == 'date-time':
            imports.add("java.time.OffsetDateTime")
            java_type = "OffsetDateTime"
        elif openapi_format == 'binary' or openapi_format == 'byte':
            # No import needed for byte[]
            java_type = "byte[]"
        else:
            # No import needed for String
            java_type = "String"
    elif openapi_type == 'integer':
        # No import needed for Long/Integer wrapper types
        java_type = "Long" if openapi_format == 'int64' else "Integer"
    elif openapi_type == 'number':
        # No import needed for Float/Double wrapper types
        java_type = "Float" if openapi_format == 'float' else "Double"
    elif openapi_type == 'boolean':
        # No import needed for Boolean wrapper type
        java_type = "Boolean"
    elif openapi_type == 'array':
        imports.add("java.util.List")
        items = schema_prop.get('items', {})
        # Recursively get type for items, passing imports set
        item_type_name = get_java_type(items, model_package, imports)
        java_type = f"List<{item_type_name}>"
    elif openapi_type == 'object':
        ref = schema_prop.get('$ref')
        if ref:
            # It's a reference to another schema (potential POJO)
            schema_name = ref.split('/')[-1]
            # Return the simple class name. Caller must handle import based on model_package.
            java_type = to_java_class_name(schema_name)
            # Ensure the referenced POJO is imported if it's in the model package
            if model_package:
                 imports.add(f"{model_package}.{java_type}")
        else:
            # Could be a map or inline object
            additional_props = schema_prop.get('additionalProperties')
            if isinstance(additional_props, dict):
                # It's a map
                imports.add("java.util.Map")
                value_type_name = get_java_type(additional_props, model_package, imports)
                java_type = f"Map<String, {value_type_name}>"
            else:
                # Inline object without $ref or additionalProperties - less defined
                # Fallback to Map<String, Object> might be safest
                imports.add("java.util.Map")
                java_type = "Map<String, Object>"

    # Return the determined simple Java type name
    return java_type

# --- End Java Generation Utilities ---

def generate_all_java_files(
    openapi_spec: OpenAPISpec,
    mapping_spec: MappingSpec,
    package_name: str,
    java_package_base_path: str,
    render_template: Callable[[str, Dict, str], None],
    schema_extraction_enabled: bool = False # Add flag from CLI
):
    """
    Orchestrates the generation of all Java source files.

    Args:
        openapi_spec: Parsed OpenAPI spec.
        mapping_spec: Parsed mapping spec.
        package_name: Base Java package name (e.g., com.example.connector).
        java_package_base_path: Filesystem path to the base package directory.
        render_template: The rendering function from GeneratorEngine.
        schema_extraction_enabled: Flag indicating if schema extraction should be generated.
    """
    print("DEBUG: TOP OF generate_all_java_files EXECUTED")

    log.info("Starting Java code generation...")
    print("DEBUG: Entering generate_all_java_files") # Existing DEBUG

    # Determine necessary operations from OpenAPI spec
    operations = _determine_operations(openapi_spec, schema_extraction_enabled)
    print(f"DEBUG: Determined operations: {operations}") # Existing DEBUG
    model_package = f"{package_name}.model"

    # --- Generate Model POJOs from OpenAPI Schemas ---
    generated_models = _generate_model_pojos(openapi_spec, package_name, java_package_base_path, render_template)

    # --- Generate Base BackendRequest/Response POJOs ---
    _generate_base_request_response_pojos(package_name, java_package_base_path, render_template)

    # --- Generate Backend Client --- [STEP 1]
    # This function now needs to return the metadata map
    client_class_name, client_method_metadata = _generate_backend_client(openapi_spec, mapping_spec, package_name, java_package_base_path, render_template)
    print(f"DEBUG: _generate_backend_client returned: {client_class_name} with metadata keys: {list(client_method_metadata.keys())}") # Add check

    # --- Generate Type Converters --- [STEP 2 partial - need to pass metadata]
    req_converter_class_name, resp_converter_class_name = _generate_type_converters(openapi_spec, mapping_spec, package_name, java_package_base_path, render_template, operations, generated_models, client_method_metadata)
    print(f"DEBUG: _generate_type_converters returned: Req={req_converter_class_name}, Resp={resp_converter_class_name}") # Add check

    # --- Generate Main Connector Class --- [STEP 3]
    _generate_main_connector(openapi_spec, mapping_spec, package_name, java_package_base_path, render_template, operations, client_class_name, req_converter_class_name, resp_converter_class_name, generated_models, client_method_metadata)
    print(f"DEBUG: Completed call to _generate_main_connector") # Add check

    log.info("Java code generation finished.")
    print("DEBUG: Exiting generate_all_java_files normally") # Existing DEBUG

def _determine_operations(openapi_spec: OpenAPISpec, schema_extraction_enabled: bool) -> Set[str]:
    """Determines which CRUD operations seem to be supported based on HTTP methods in paths."""
    print("DEBUG: Entering _determine_operations")
    operations = set()
    # Always include TestConnect
    operations.add("TestConnect")

    try: # Add try-except here just in case
        paths = openapi_spec.get_paths()
        for path, path_item in paths.items():
            # Check methods defined directly on the path item
            methods = {k.upper() for k in path_item.keys() if k.upper() in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']}
            # TODO: Also consider methods defined under path_item.get('operations', {}) if structure differs

            if 'GET' in methods:
                operations.add("Search")
            if 'POST' in methods:
                operations.add("Insertion")
            if 'PUT' in methods or 'PATCH' in methods:
                operations.add("Modification")
            if 'DELETE' in methods:
                operations.add("Deletion")
    except Exception as e:
        print(f"ERROR inside _determine_operations: {e}")
        import traceback
        traceback.print_exc()
        # Optionally re-raise
        raise

    # Add SchemaExtraction if enabled via CLI flag
    if schema_extraction_enabled:
         operations.add("SchemaExtraction")
         log.info("Schema extraction operation enabled by flag.")

    log.info(f"Detected potential operations: {operations}")
    print(f"DEBUG: Exiting _determine_operations, found: {operations}") # DEBUG
    return operations

def _generate_model_pojos(openapi_spec: OpenAPISpec, package_name: str, base_path: str, render: Callable) -> Set[str]:
    """Generates Java POJO classes from OpenAPI schemas. Returns names of generated classes."""
    log.info("  Generating Model POJOs...")
    print("DEBUG: Entering _generate_model_pojos") # DEBUG
    model_path = os.path.join(base_path, 'model')
    os.makedirs(model_path, exist_ok=True)
    model_package = f"{package_name}.model"
    generated_models = set()

    schemas = openapi_spec.get_schemas()
    if not schemas:
        log.warning("  No schemas found in OpenAPI spec to generate POJOs.")
        print("DEBUG: No schemas found in OpenAPI spec.") # DEBUG
        return generated_models

    print(f"DEBUG: Found {len(schemas)} schemas in OpenAPI spec: {list(schemas.keys())}") # DEBUG

    for schema_name, schema_details in schemas.items():
        # Generate POJO only for object types (or refs treated as objects)
        # Skip basic types that might appear in components/schemas
        schema_type = schema_details.get('type', 'object')
        if schema_type == 'object' or '$ref' in schema_details:
            class_name = to_java_class_name(schema_name)
            generated_models.add(class_name)
            fields = []
            # Initialize imports for this specific POJO
            imports = set([
                # Consider adding common imports like lombok if used
                # "lombok.Data",
                # "lombok.NoArgsConstructor",
                # "lombok.AllArgsConstructor",
                JACKSON_JSON_PROPERTY_ANNOTATION # Add Jackson import
            ])

            openapi_properties = schema_details.get('properties', {})
            for prop_name, prop_details in openapi_properties.items():
                field_name = to_java_variable_name(prop_name)
                # Get Java type and update imports set
                java_type_simple = get_java_type(prop_details, model_package, imports)
                field = {
                    'name': field_name,
                    'type': java_type_simple,
                    'json_property': prop_name,
                    'getter': f"get{field_name.capitalize()}",
                    'setter': f"set{field_name.capitalize()}"
                    # TODO: Add description, required status, constraints if needed
                }
                fields.append(field)

            # Determine constructor args (e.g., for required fields)
            # TODO: Implement logic for required fields if needed for constructors
            constructor_args = []

            context = {
                'package_name': model_package,
                'class_name': class_name,
                'imports': sorted(list(imports)),
                'fields': fields,
                'constructor_args': constructor_args,
                # Add flags for lombok if used
                'use_lombok_data': False,
                'use_lombok_constructors': False
            }

            output_file = os.path.join(model_path, f"{class_name}.java")
            render('java/Pojo.java.j2', context, output_file)
        else:
            log.debug(f"  Skipping POJO generation for schema '{schema_name}' as its type is '{schema_type}'.")

    print(f"DEBUG: Generated model POJO names: {generated_models}") # DEBUG
    return generated_models

def _generate_base_request_response_pojos(package_name: str, base_path: str, render: Callable):
    """Generates the BackendRequest and BackendResponse POJOs."""
    log.info("  Generating Base Request/Response POJOs...")
    print("DEBUG: Entering _generate_base_request_response_pojos") # DEBUG
    model_path = os.path.join(base_path, 'model')
    model_package = f"{package_name}.model"

    # --- Generate BackendRequest --- [STEP 2 partial]
    request_imports = set([
        "java.util.Map",
        "java.util.List",
        "java.util.Set"
    ])
    request_fields = [
        # Fields to hold information extracted by the LdapToBackendRequestConverter
        {'name': 'httpMethod', 'type': 'String'},
        {'name': 'pathTemplate', 'type': 'String'}, # Original path template (e.g., /users/{id})
        {'name': 'pathParams', 'type': 'Map<String, String>'}, # Resolved path parameters
        {'name': 'queryParams', 'type': 'Map<String, String>'}, # API query parameters
        {'name': 'requestBody', 'type': 'Object'}, # POJO or structure for request body
        {'name': 'headers', 'type': 'Map<String, String>'}, # Specific headers if needed
        {'name': 'targetObjectClass', 'type': 'String'}, # LDAP ObjectClass being processed
        {'name': 'resourceId', 'type': 'String'}, # Extracted primary key/ID, often for BASE scope
        {'name': 'fieldsToRetrieve', 'type': 'List<String>'}, # API fields requested (if mapping from LDAP attributes)
        # {'name': 'originalLdapRequest', 'type': 'LdapRequest'}, # Optionally store original

        # ** NEW FIELD ** for target client method
        {'name': 'targetClientMethodName', 'type': 'String'}, # Name of the client method to call

        # Old field - deprecate/remove in favor of targetClientMethodName
        # {'name': 'operationHint', 'type': 'String'} # Hint for which client method (e.g., operationId)
    ]
    # Add imports for field types
    request_imports.add("java.util.Map")
    request_imports.add("java.util.List")
    request_imports.add("java.util.Set")

    # Add getter/setter info
    for field in request_fields:
        cap_name = field['name'][0].upper() + field['name'][1:]
        field['getterName'] = f"get{cap_name}"
        field['setterName'] = f"set{cap_name}"
        field['original_name'] = field['name']

    request_context = {
        'package_name': model_package,
        'class_name': BACKEND_REQUEST_BASE,
        'imports': sorted(list(request_imports)),
        'fields': request_fields,
        'constructor_args': [], # Basic constructor
        'use_lombok_data': False,
        'use_lombok_constructors': False
    }
    output_file_req = os.path.join(model_path, f"{BACKEND_REQUEST_BASE}.java")
    render('java/Pojo.java.j2', request_context, output_file_req)

    # --- Generate BackendResponse ---
    response_imports = set([
        "java.util.Map",
        "java.util.List"
    ])
    response_fields = [
        # Fields to hold information extracted from the client's response
        {'name': 'statusCode', 'type': 'int'},
        {'name': 'payload', 'type': 'Object'}, # Deserialized POJO or List<POJO>
        {'name': 'headers', 'type': 'Map<String, List<String>>'} # Response headers
        # {'name': 'originalBackendRequest', 'type': BACKEND_REQUEST_BASE}, # Optionally link back
    ]
    # Add imports for field types
    response_imports.add("java.util.Map")
    response_imports.add("java.util.List")

    # Add getter/setter info
    for field in response_fields:
        cap_name = field['name'][0].upper() + field['name'][1:]
        field['getterName'] = f"get{cap_name}"
        field['setterName'] = f"set{cap_name}"
        field['original_name'] = field['name']

    response_context = {
        'package_name': model_package,
        'class_name': BACKEND_RESPONSE_BASE,
        'imports': sorted(list(response_imports)),
        'fields': response_fields,
        'constructor_args': [], # Basic constructor
        'use_lombok_data': False,
        'use_lombok_constructors': False
    }
    output_file_resp = os.path.join(model_path, f"{BACKEND_RESPONSE_BASE}.java")
    render('java/Pojo.java.j2', response_context, output_file_resp)

    print(f"DEBUG: Generated {BACKEND_REQUEST_BASE}.java and {BACKEND_RESPONSE_BASE}.java")

def _generate_backend_client(
    openapi_spec: OpenAPISpec,
    mapping_spec: MappingSpec,
    package_name: str,
    base_path: str,
    render: Callable
) -> tuple[str, dict]: # Return client class name and method metadata
    """Generates the Backend HTTP Client class. Returns class name and method metadata map."""
    log.info("  Generating Backend Client...")
    print("DEBUG: Entering _generate_backend_client") # DEBUG
    client_path = os.path.join(base_path, 'client')
    os.makedirs(client_path, exist_ok=True)
    client_package = f"{package_name}.client"
    model_package = f"{package_name}.model"

    # Use API title or a default for class name
    api_title = openapi_spec.data.get('info', {}).get('title', 'GenericApi')
    class_name = f"{to_java_class_name(api_title)}Client"

    imports = set([
        f"{model_package}.*", # Import all models
        MANAGED_COMPONENT_ANNOTATION,
        INJECT_ANNOTATION,
        PROPERTIES_ANNOTATION,
        INJECTABLE_PROPS_ENUM,
        RESPONSE_ENTITY_CLASS,
        RESPONSE_STATUS_ENUM,
        "java.io.IOException",
        "java.util.List",
        "java.util.Map",
        "java.util.Objects",
        "java.util.concurrent.TimeUnit",
        "java.util.concurrent.atomic.AtomicReference", # For potential OAuth
        "javax.annotation.PostConstruct",
        "okhttp3.*",
        "org.slf4j.Logger",
        "org.slf4j.LoggerFactory",
        "com.fasterxml.jackson.databind.ObjectMapper",
        "com.fasterxml.jackson.datatype.jsr310.JavaTimeModule"
    ])

    # Process paths to create methods
    methods = []
    client_method_metadata = {} # [STEP 1] Initialize metadata map

    paths = openapi_spec.get_paths()
    schemas = openapi_spec.get_schemas() # Need this to resolve response types

    for path_template, path_details in paths.items():
        common_params = path_details.get('parameters', [])

        for http_method, op_details in path_details.items():
            if http_method.upper() not in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
                continue # Skip non-method keys like 'parameters'

            operation_id = op_details.get('operationId')
            if not operation_id:
                # Generate an ID if missing (less ideal)
                operation_id = f"{http_method.lower()}{path_template.replace('/', '_').replace('{', '_').replace('} ', '')}"
                log.warning(f"OperationId missing for {http_method.upper()} {path_template}, generated: {operation_id}")

            method_name = to_java_variable_name(operation_id)
            summary = op_details.get('summary', '')
            params = [] # Path, query, header params for the method signature
            all_op_params = common_params + op_details.get('parameters', []) # Combine path and op params

            path_params_in_sig = set()

            for param_details in all_op_params:
                param_name = param_details.get('name')
                param_in = param_details.get('in')
                param_schema = param_details.get('schema', {})

                if param_in in ['path', 'query']:
                    java_param_name = to_java_variable_name(param_name)
                    java_param_type = get_java_type(param_schema, model_package, imports)
                    params.append({
                        'name': java_param_name,
                        'type': java_param_type,
                        'original_name': param_name,
                        'in': param_in,
                        'description': param_details.get('description', '')
                    })
                    if param_in == 'path':
                         path_params_in_sig.add(java_param_name)
                # TODO: Handle header params if needed in method sig (less common)

            # Handle request body
            request_body_details = op_details.get('requestBody')
            request_body_param = None
            request_content_type = None
            if request_body_details:
                # Find the JSON content type
                json_content = request_body_details.get('content', {}).get('application/json')
                if json_content and 'schema' in json_content:
                    request_content_type = 'application/json'
                    body_schema = json_content['schema']
                    body_type = get_java_type(body_schema, model_package, imports)
                    # Use a standard name like 'body' or 'requestBody'
                    body_param_name = "body" # Or derive from schema name?
                    params.append({
                        'name': body_param_name,
                        'type': body_type,
                        'original_name': body_param_name, # Placeholder
                        'in': 'body',
                        'description': 'Request body'
                    })
                    request_body_param = params[-1] # Reference the added param
                else:
                     log.warning(f"Operation {operation_id} has requestBody but no application/json schema found. Body parameter skipped.")
                     # TODO: Handle other content types if necessary (e.g., form data)

            # Determine return type
            return_type = "void" # Default for methods like DELETE without response body
            return_type_simple = "void"
            response_content_type = None
            response_pojo_type = None # Track the POJO type returned

            success_response = op_details.get('responses', {}).get('200') or op_details.get('responses', {}).get('201')
            if success_response:
                json_content = success_response.get('content', {}).get('application/json')
                if json_content and 'schema' in json_content:
                    response_content_type = 'application/json'
                    response_schema = json_content['schema']
                    return_type_simple = get_java_type(response_schema, model_package, imports)
                    # Wrap in BackendResponse
                    imports.add(f"{model_package}.{BACKEND_RESPONSE_BASE}")
                    return_type = BACKEND_RESPONSE_BASE # All methods return the wrapper
                    response_pojo_type = return_type_simple # Store the actual payload type
                elif success_response.get('description'): # Has description but no content schema
                     # Still return BackendResponse, payload will be null
                     imports.add(f"{model_package}.{BACKEND_RESPONSE_BASE}")
                     return_type = BACKEND_RESPONSE_BASE
                     response_pojo_type = 'Void' # Indicate no expected payload body

            # Handle DELETE 204 No Content
            if http_method.upper() == 'DELETE' and '204' in op_details.get('responses', {}):
                 imports.add(f"{model_package}.{BACKEND_RESPONSE_BASE}")
                 return_type = BACKEND_RESPONSE_BASE # Return wrapper even for 204
                 response_pojo_type = 'Void' # Indicate no expected payload body


            method_data = {
                'name': method_name,
                'summary': summary,
                'http_method': http_method.upper(),
                'endpoint_path_template': path_template,
                'params': params,
                'path_params_in_sig': list(path_params_in_sig),
                'request_body_param': request_body_param, # Store ref to body param info
                'return_type': return_type, # Always BackendResponse (or void if truly no return)
                'return_type_simple': return_type_simple, # Actual Java type of response payload
                'request_content_type': request_content_type,
                'response_content_type': response_content_type
            }
            methods.append(method_data)

            # [STEP 1] Store metadata keyed by operationId (or fallback ID)
            client_method_metadata[operation_id] = {
                "name": method_name,
                "signature": [(p['type'], p['name']) for p in params], # Store type and name of params
                "return_type": return_type, # Wrapper type
                "payload_type": response_pojo_type or return_type_simple # Actual POJO type or Void/primitive
            }

    # Add Test Connection method
    test_connect_method = {
        'name': 'testConnection',
        'summary': 'Tests the connection to the API.',
        'http_method': 'GET', # Assumes a simple GET is sufficient
        'endpoint_path_template': None, # Client chooses an endpoint
        'params': [],
        'path_params_in_sig': [],
        'request_body_param': None,
        'return_type': 'boolean', # Simple boolean return
        'return_type_simple': 'boolean',
        'is_test_connection': True
    }
    # Find a simple GET endpoint to use for test connection, preferably root or /items
    # Simplistic choice: use the first generated GET method's details if possible
    first_get_method = next((m for m in methods if m['http_method'] == 'GET' and not m['params']), None) # Prefer GET with no params
    if not first_get_method:
        first_get_method = next((m for m in methods if m['http_method'] == 'GET'), None) # Any GET

    if first_get_method:
        test_connect_method['endpoint_path_template'] = first_get_method['endpoint_path_template']
        test_connect_method['target_call_name'] = first_get_method['name'] # Call this generated method
        test_connect_method['target_call_args'] = {p['name']:None for p in first_get_method['params']} # Pass null/default for args
        log.info(f"Using endpoint '{test_connect_method['endpoint_path_template']}' for testConnection.")
    else:
        log.warning("Could not find suitable GET endpoint for testConnection method. It will likely fail.")
        # Use a placeholder path
        test_connect_method['endpoint_path_template'] = "/" # Guess root?
        test_connect_method['target_call_name'] = None

    methods.append(test_connect_method)

    # Determine authentication details for the client template
    auth_details = _prepare_auth_details(openapi_spec)

    context = {
        'package_name': client_package,
        'class_name': class_name,
        'imports': sorted(list(imports)),
        'methods': methods,
        'model_package': model_package,
        'auth_details': auth_details,
        'connection_properties_enum': f"{INJECTABLE_PROPS_ENUM}.CONNECTION_CONFIGURATION" # Pass enum reference
    }

    output_file = os.path.join(client_path, f"{class_name}.java")
    render('java/Client.java.j2', context, output_file)

    print(f"DEBUG: Generated {class_name}.java") # DEBUG
    return class_name, client_method_metadata # [STEP 1] Return metadata

def _prepare_auth_details(openapi_spec: OpenAPISpec) -> Dict:
    """Analyzes security schemes and returns details for the client template."""
    auth_details = {
        'needs_api_key': False,
        'api_key_name': None,
        'api_key_in': None,
        'api_key_prop_name': None,
        'needs_http_basic': False,
        'http_user_prop_name': None,
        'http_pass_prop_name': None,
        'needs_bearer_token': False,
        'bearer_token_prop_name': None,
        'needs_oauth': False, # TODO: Add OAuth support details
    }
    schemes = openapi_spec.get_security_schemes()
    global_security = openapi_spec.data.get('security', [])
    used_scheme_names = set()
    for sec_req in global_security:
        used_scheme_names.update(sec_req.keys())

    for name, scheme in schemes.items():
        if name not in used_scheme_names:
            continue # Skip unused schemes

        scheme_type = scheme.get('type')
        if scheme_type == 'apiKey':
            auth_details['needs_api_key'] = True
            auth_details['api_key_name'] = scheme.get('name')
            auth_details['api_key_in'] = scheme.get('in') # header or query
            # Generate a property name based on the scheme name/key name
            auth_details['api_key_prop_name'] = f"{to_java_class_name(scheme.get('name', name))}ApiKey"
            log.info(f"Configuring client for API Key auth (Name: {auth_details['api_key_name']}, In: {auth_details['api_key_in']})")
        elif scheme_type == 'http':
            http_scheme = scheme.get('scheme')
            if http_scheme == 'basic':
                auth_details['needs_http_basic'] = True
                auth_details['http_user_prop_name'] = "httpBasicUsername" # Standardized prop name
                auth_details['http_pass_prop_name'] = "httpBasicPassword"
                log.info("Configuring client for HTTP Basic auth.")
            elif http_scheme == 'bearer':
                auth_details['needs_bearer_token'] = True
                auth_details['bearer_token_prop_name'] = "bearerToken" # Standardized prop name
                log.info("Configuring client for Bearer Token auth.")
        elif scheme_type == 'oauth2':
            auth_details['needs_oauth'] = True
            log.warning("OAuth2 scheme detected, but full support is not implemented in generator.")
            # TODO: Extract flow details, scopes, token URL etc.

    return auth_details

def _generate_type_converters(
    openapi_spec: OpenAPISpec,
    mapping_spec: MappingSpec,
    package_name: str,
    base_path: str,
    render: Callable,
    operations: Set[str],
    generated_models: Set[str],
    client_method_metadata: Dict[str, Dict] # [STEP 2] Receive client metadata
) -> tuple[Optional[str], Optional[str]]:
    """Generates the LdapToBackendRequestConverter and BackendToLdapResponseConverter classes."""
    log.info("  Generating Type Converters...")
    print("DEBUG: Entering _generate_type_converters") # DEBUG
    converter_path = os.path.join(base_path, 'converter')
    os.makedirs(converter_path, exist_ok=True)
    converter_package = f"{package_name}.converter"
    model_package = f"{package_name}.model"

    req_converter_class_name = "LdapToBackendRequestConverter"
    resp_converter_class_name = "BackendToLdapResponseConverter"

    # --- Generate LdapToBackendRequestConverter --- [STEP 2]
    req_imports = set([
        f"{model_package}.*",
        MANAGED_COMPONENT_ANNOTATION,
        CONVERTER_INTERFACE,
        f"{SDK_PACKAGE}.dn.DN",
        f"{SDK_PACKAGE}.filter.Filter",
        f"{SDK_PACKAGE}.filter.FilterType",
        f"{SDK_PACKAGE}.filter.FilterVisitor",
        LDAP_REQUEST_CLASS,
        SEARCH_REQUEST_CLASS,
        ADD_REQUEST_CLASS,
        MODIFY_REQUEST_CLASS,
        DELETE_REQUEST_CLASS,
        "java.util.ArrayList",
        "java.util.Collections",
        "java.util.HashMap",
        "java.util.List",
        "java.util.Map",
        "java.util.Set",
        "javax.naming.NamingException",
        "javax.naming.directory.Attribute",
        "javax.naming.directory.Attributes",
        "javax.naming.directory.ModificationItem",
        "javax.naming.directory.DirContext", # For modification op constants
        "org.slf4j.Logger",
        "org.slf4j.LoggerFactory",
        "com.fasterxml.jackson.databind.ObjectMapper", # For mapping load and POJO mapping
        # For reflection in mapAttributesToPojo
        "java.lang.reflect.Method",
        "java.lang.reflect.InvocationTargetException",
        "java.math.BigDecimal", # For number conversions
        "java.time.LocalDate",
        "java.time.OffsetDateTime",
        "java.time.format.DateTimeParseException"
    ])
    # Add specific POJO imports
    # for model in generated_models:
    #      req_imports.add(f"{model_package}.{model}")

    # Context needs info to find the right client method
    req_context = {
        'package_name': converter_package,
        'class_name': req_converter_class_name,
        'imports': sorted(list(req_imports)),
        'input_type': 'LdapRequest', # Base type
        'output_type': BACKEND_REQUEST_BASE, # Base type
        'converter_type': 'request', # Flag for template conditional logic
        'model_package': model_package,
        # ** Pass client method metadata to the template ** [STEP 2]
        'client_method_metadata_json': json.dumps(client_method_metadata or {})
    }

    output_file_req = os.path.join(converter_path, f"{req_converter_class_name}.java")
    # Assuming Converter.java.j2 handles both request and response based on 'converter_type'
    render('java/Converter.java.j2', req_context, output_file_req)

    # --- Generate BackendToLdapResponseConverter ---
    resp_imports = set([
        f"{model_package}.*",
        MANAGED_COMPONENT_ANNOTATION,
        CONVERTER_INTERFACE,
        f"{SDK_PACKAGE}.dn.DN",
        RESPONSE_ENTITY_CLASS,
        RESPONSE_STATUS_ENUM,
        SEARCH_RESULT_ENTRY_CLASS,
        "java.lang.reflect.Method",
        "java.util.ArrayList",
        "java.util.Collection",
        "java.util.Collections",
        "java.util.List",
        "java.util.Map",
        "java.util.Optional",
        "javax.naming.NamingException",
        "javax.naming.directory.Attribute",
        "javax.naming.directory.Attributes",
        "javax.naming.directory.BasicAttribute",
        "javax.naming.directory.BasicAttributes",
        "org.slf4j.Logger",
        "org.slf4j.LoggerFactory",
        "com.fasterxml.jackson.databind.ObjectMapper" # For mapping load
    ])

    # The response converter might return different types (ResponseEntity, List<SearchResultEntry>)
    # The TypeConverter interface takes specific types. Here, we define it as converting
    # BackendResponse -> Object, and the logic inside determines the actual return.
    # This matches the explicit call pattern used in the Connector template for search.
    resp_context = {
        'package_name': converter_package,
        'class_name': resp_converter_class_name,
        'imports': sorted(list(resp_imports)),
        'input_type': BACKEND_RESPONSE_BASE,
        'output_type': 'Object', # Generic output, convert method determines actual type
        'converter_type': 'response', # Flag for template conditional logic
        'model_package': model_package,
        'ldap_search_result_entry_type_simple': SEARCH_RESULT_ENTRY_CLASS.split('.')[-1],
        'ldap_response_entity_type_simple': RESPONSE_ENTITY_CLASS.split('.')[-1],
        'response_status_enum_simple': RESPONSE_STATUS_ENUM.split('.')[-1],
        'client_method_metadata_json': json.dumps(client_method_metadata or {}) # Pass metadata for context if needed
    }

    output_file_resp = os.path.join(converter_path, f"{resp_converter_class_name}.java")
    render('java/Converter.java.j2', resp_context, output_file_resp)

    print(f"DEBUG: Generated {req_converter_class_name}.java and {resp_converter_class_name}.java")
    return req_converter_class_name, resp_converter_class_name

def _generate_main_connector(
    openapi_spec: OpenAPISpec,
    mapping_spec: MappingSpec,
    package_name: str,
    base_path: str,
    render: Callable,
    operations: Set[str],
    client_class_name: Optional[str],
    req_converter_class_name: Optional[str],
    resp_converter_class_name: Optional[str],
    generated_models: Set[str],
    client_method_metadata: Dict[str, Dict] # [STEP 3] Receive client metadata
):
    """Generates the main Connector class."""
    log.info("  Generating Main Connector Class...")
    print("DEBUG: Entering _generate_main_connector") # DEBUG

    api_title = openapi_spec.data.get('info', {}).get('title', 'GenericApi')
    class_name = f"{to_java_class_name(api_title)}Connector"

    model_package = f"{package_name}.model"
    client_package = f"{package_name}.client"
    converter_package = f"{package_name}.converter"

    imports = set([
        MANAGED_COMPONENT_ANNOTATION,
        CUSTOM_CONNECTOR_ANNOTATION,
        INJECT_ANNOTATION,
        f"{model_package}.*",
        RESPONSE_ENTITY_CLASS,
        RESPONSE_STATUS_ENUM,
        SEARCH_RESULT_ENTRY_CLASS,
        "java.io.IOException", # For catching client exceptions
        "java.util.Collections",
        "java.util.List",
        "java.util.Map", # For metadata loading
        "org.slf4j.Logger",
        "org.slf4j.LoggerFactory"
    ])

    interfaces = []
    injected_fields = []

    # Add Client dependency
    if client_class_name:
        imports.add(f"{client_package}.{client_class_name}")
        client_var_name = to_java_variable_name(client_class_name)
        injected_fields.append({'type': client_class_name, 'name': client_var_name})
    else:
        client_var_name = "client" # Fallback name
        log.warning("Client class name not provided to main connector generator.")

    # Add Converter dependencies if generated
    if req_converter_class_name:
        imports.add(f"{converter_package}.{req_converter_class_name}")
        # Converters usually not injected into main connector if SDK handles pipeline
    if resp_converter_class_name:
        imports.add(f"{converter_package}.{resp_converter_class_name}")
        # Need to inject response converter for explicit search result handling
        resp_converter_var_name = to_java_variable_name(resp_converter_class_name)
        # injected_fields.append({'type': resp_converter_class_name, 'name': resp_converter_var_name})
        # Note: The template Connector.java.j2 explicitly injects this as 'respConverter'

    # Add operation interfaces based on detected operations
    backend_request_type_simple = BACKEND_REQUEST_BASE
    backend_response_type_simple = BACKEND_RESPONSE_BASE
    ldap_search_result_entry_type_simple = SEARCH_RESULT_ENTRY_CLASS.split('.')[-1]
    ldap_response_entity_type_simple = RESPONSE_ENTITY_CLASS.split('.')[-1]

    # Assuming usage of BackendRequest/Response types with converters
    if "Search" in operations:
        imports.add(READ_OPERATIONS_INTERFACE)
        interfaces.append(f"{READ_OPERATIONS_INTERFACE.split('.')[-1]}<{backend_request_type_simple}, List<{ldap_search_result_entry_type_simple}>>")
    if "Insertion" in operations:
        imports.add(CREATE_OPERATIONS_INTERFACE)
        interfaces.append(f"{CREATE_OPERATIONS_INTERFACE.split('.')[-1]}<{backend_request_type_simple}, {ldap_response_entity_type_simple}<{backend_response_type_simple}>>")
    if "Modification" in operations:
        imports.add(MODIFY_OPERATIONS_INTERFACE)
        interfaces.append(f"{MODIFY_OPERATIONS_INTERFACE.split('.')[-1]}<{backend_request_type_simple}, {ldap_response_entity_type_simple}<{backend_response_type_simple}>>")
    if "Deletion" in operations:
        imports.add(DELETE_OPERATIONS_INTERFACE)
        interfaces.append(f"{DELETE_OPERATIONS_INTERFACE.split('.')[-1]}<{backend_request_type_simple}, {ldap_response_entity_type_simple}<?>>")
    if "TestConnect" in operations:
        imports.add(TEST_CONNECT_OPERATIONS_INTERFACE)
        interfaces.append(f"{TEST_CONNECT_OPERATIONS_INTERFACE.split('.')[-1]}<?>")
    if "SchemaExtraction" in operations:
         imports.add(SCHEMA_EXTRACTION_OPERATIONS_INTERFACE)
         interfaces.append(f"{SCHEMA_EXTRACTION_OPERATIONS_INTERFACE.split('.')[-1]}")
         # Add imports needed for schema extraction implementation/placeholders
         imports.add("java.util.ArrayList")
         # Potentially add SDK schema definition classes if known
         # imports.add("com.radiantlogic.iddm.connector.sdk.schema.*")


    # Prepare context for the template [STEP 3]
    context = {
        'package_name': package_name,
        'class_name': class_name,
        'imports': sorted(list(imports)),
        'interfaces': interfaces,
        'injected_fields': injected_fields,
        'operations': operations,
        'meta_json_path': "META-INF/connector/meta.json", # Standard path
        'backend_request_type': backend_request_type_simple,
        'backend_response_type': backend_response_type_simple,
        'ldap_search_result_entry_type': ldap_search_result_entry_type_simple,
        'ldap_response_entity_type': ldap_response_entity_type_simple,
        'response_status_enum_simple': RESPONSE_STATUS_ENUM.split('.')[-1],
        'client_var_name': client_var_name,
        'resp_converter_class_name': resp_converter_class_name, # Pass name for explicit injection
        'generate_schema_extraction': "SchemaExtraction" in operations,
        # ** Pass client method metadata as JSON string ** [STEP 3]
        'client_method_metadata_json': json.dumps(client_method_metadata or {})
    }

    output_file = os.path.join(base_path, f"{class_name}.java")
    render('java/Connector.java.j2', context, output_file)
    print(f"DEBUG: Generated {class_name}.java") # DEBUG
