from typing import Dict, Any, List, Optional
import logging
import json # For potential JSONPath processing if needed later
import re

# Ensure absolute imports are used
from parsers.openapi_parser import OpenAPISpec
from parsers.mapping_parser import MappingSpec

# Attempt to import jsonpath_ng
try:
    from jsonpath_ng import parse as jsonpath_parse
    from jsonpath_ng.exceptions import JsonPathParserError
    JSONPATH_SUPPORTED = True
except ImportError:
    log.warning("jsonpath-ng library not found. JSONPath mapping support is disabled. pip install jsonpath-ng")
    jsonpath_parse = None
    JsonPathParserError = Exception
    JSONPATH_SUPPORTED = False

log = logging.getLogger(__name__)

# Mapping from OpenAPI types/formats to ORX types
# Keys are tuples: (openapi_type, openapi_format) or just (openapi_type, None)
# Based on common ORX types: string, integer, long, double, boolean, generalizedTime, binary
# See ORX documentation for full list and details.
ORX_TYPE_MAP = {
    # Type only
    ("string", None): "string",
    ("integer", None): "integer", # Default integer
    ("number", None): "double",  # Default floating point
    ("boolean", None): "boolean",
    ("array", None): "string",    # Default for arrays (often multi-valued string)
    ("object", None): "string",   # Default for objects (e.g., JSON string)

    # Type + Format combinations
    ("string", "date-time"): "generalizedTime",
    ("string", "date"): "generalizedTime", # ORX typically uses generalizedTime
    ("string", "byte"): "binary",          # Base64 encoded string -> binary
    ("string", "binary"): "binary",
    ("integer", "int32"): "integer",
    ("integer", "int64"): "long",
    ("number", "float"): "double", # ORX often just uses double
    ("number", "double"): "double",
}

# Fallback type if no match found
DEFAULT_ORX_TYPE = "string"

def _generate_default_ldap_name(openapi_prop_name: str) -> str:
    """Generates a default LDAP attribute name from an OpenAPI property name.
       Simple version: just use the property name.
       Could be refined (e.g., camelCase to hyphenated, add prefix).
    """
    # Example: Convert camelCase to lower-hyphen potentially?
    # name = re.sub(r'(.)([A-Z][a-z]+)', r'\1-\2', openapi_prop_name)
    # name = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', name).lower()
    # For now, keep it simple:
    return openapi_prop_name # Or add a prefix like 'api-' + openapi_prop_name

def _get_openapi_schema_details(openapi_spec: OpenAPISpec, schema_ref: str) -> Optional[Dict[str, Any]]:
    """Resolves a simple $ref link within the components/schemas or definitions."""
    if not schema_ref or not schema_ref.startswith('#/components/schemas/') and not schema_ref.startswith('#/definitions/'):
        log.warning(f"Cannot resolve non-local schema reference: {schema_ref}")
        return None

    parts = schema_ref.split('/')
    schema_name = parts[-1]
    schemas = openapi_spec.get_schemas()
    return schemas.get(schema_name)

def _get_openapi_definition_by_path(schema: Dict[str, Any], json_path: str) -> Optional[Dict[str, Any]]:
    """Attempts to find the OpenAPI schema definition fragment corresponding to a JSONPath.
       NOTE: This is a basic implementation. It doesn't fully resolve $refs within the path.
    """
    if not JSONPATH_SUPPORTED:
        return None

    try:
        path_expr = jsonpath_parse(json_path)
        # We assume the path targets a property within the schema. We need the *definition*.
        # This is complex. For simple paths like '$.name' or '$.address.street', we can try.
        # Path: '$.prop1.prop2' -> Find schema[properties][prop1][properties][prop2]
        current_def = schema
        if isinstance(path_expr, jsonpath_ng.fields.Fields):
             path_parts = str(path_expr).split('.') # Simple dot notation split
             for part in path_parts:
                 if part == '$': continue
                 if current_def.get('type') == 'object' and 'properties' in current_def:
                      current_def = current_def['properties'].get(part)
                 elif current_def.get('type') == 'array' and 'items' in current_def and part.isdigit():
                      # Path into array - use item definition
                      current_def = current_def['items']
                      # If path continues into array item's properties, need further logic
                 else:
                     current_def = None # Cannot navigate further

                 if current_def is None:
                     break
             return current_def
        else:
            # Handle more complex JSONPath expressions (filters, wildcards) - Very difficult to map back to schema def
            log.warning(f"Cannot reliably find OpenAPI definition for complex JSONPath: {json_path}")
            return None # Cannot determine definition for complex paths easily

    except (JsonPathParserError, AttributeError, KeyError, IndexError) as e:
        log.warning(f"Error processing JSONPath '{json_path}' to find schema definition: {e}")
        return None
    return None

def _infer_attribute_type(prop_details: Dict[str, Any], attr_mapping: Dict[str, Any]) -> str:
    """Infers the ORX attribute type from OpenAPI schema property details and mapping overrides."""
    if attr_mapping.get('typeOverride'):
        return attr_mapping['typeOverride']

    openapi_type = prop_details.get('type', 'string')
    openapi_format = prop_details.get('format')

    if openapi_type == 'array':
        items_details = prop_details.get('items', {})
        items_type = items_details.get('type', 'string')
        items_format = items_details.get('format')
        # Get type based on array items, default to string array (multi-valued string)
        # ORX represents multi-valued attributes, the type is the type of *each* value.
        # If the items have a specific format, use it.
        item_orx_type = ORX_TYPE_MAP.get((items_type, items_format),
                                        ORX_TYPE_MAP.get((items_type, None), DEFAULT_ORX_TYPE))
        return item_orx_type # The type definition in ORX refers to the type of each value in the multi-valued attribute

    # Look for specific type+format combination first
    orx_type = ORX_TYPE_MAP.get((openapi_type, openapi_format))
    if orx_type:
        return orx_type

    # Fallback to type only
    orx_type = ORX_TYPE_MAP.get((openapi_type, None))
    if orx_type:
        return orx_type

    # Final fallback
    log.debug(f"Unknown OpenAPI type/format combination: type='{openapi_type}', format='{openapi_format}'. Defaulting to '{DEFAULT_ORX_TYPE}'.")
    return DEFAULT_ORX_TYPE

def prepare_schema_context(openapi_spec: OpenAPISpec, mapping_spec: MappingSpec) -> Dict[str, Any]:
    """
    Prepares the context dictionary needed to render the schema.orx template.

    Generates attributes based *only* on the attributes defined in the mapping_spec.
    It uses the mapping's jsonPath to find the corresponding definition within
    the linked OpenAPI schema to infer type and other details.

    Args:
        openapi_spec: The parsed OpenAPI specification object.
        mapping_spec: The parsed mapping specification object.

    Returns:
        A dictionary containing data for the Jinja2 template.
    """
    object_classes = []
    defined_ldap_ocs = mapping_spec.get_ldap_object_classes()

    if not defined_ldap_ocs:
        log.warning("No object classes defined in the mapping file. Schema will be empty.")
        return {"object_classes": []}

    all_openapi_schemas = openapi_spec.get_schemas()

    for ldap_oc_name in defined_ldap_ocs:
        oc_mapping = mapping_spec.get_object_class_mapping(ldap_oc_name)
        if not oc_mapping:
            log.warning(f"Missing mapping details for object class: {ldap_oc_name}")
            continue

        # Determine the source OpenAPI schema
        # Assumption: mapping provides a direct reference or name
        openapi_schema_ref = oc_mapping.get('openApiSchemaRef') # e.g., "#/components/schemas/User"
        openapi_schema_name = oc_mapping.get('openApiSchemaName') # e.g., "User"
        source_schema = None

        if openapi_schema_ref:
            source_schema = _get_openapi_schema_details(openapi_spec, openapi_schema_ref)
        elif openapi_schema_name:
            source_schema = all_openapi_schemas.get(openapi_schema_name)
        else:
            log.warning(f"No OpenAPI schema reference/name found for object class: {ldap_oc_name}")
            continue # Cannot determine attributes without a source schema

        if not source_schema:
            log.warning(f"Could not find or resolve OpenAPI schema for {ldap_oc_name} (Ref: {openapi_schema_ref}, Name: {openapi_schema_name})")
            continue

        attributes = []
        primary_key_ldap_attr = oc_mapping.get('primaryKeyLdapAttribute')
        mapped_attributes_list = oc_mapping.get('attributes', [])

        # Iterate through the attributes DEFINED IN THE MAPPING FILE
        for attr_mapping in mapped_attributes_list:
            ldap_attr_name = attr_mapping.get('ldapName')
            if not ldap_attr_name:
                log.warning(f"Attribute mapping found under OC '{ldap_oc_name}' is missing 'ldapName'. Skipping.")
                continue

            json_path = attr_mapping.get('jsonPath')
            openapi_prop_name = attr_mapping.get('openApiPropertyName')

            if not json_path and not openapi_prop_name:
                 log.warning(f"Attribute '{ldap_attr_name}' for OC '{ldap_oc_name}' has neither 'jsonPath' nor 'openApiPropertyName'. Cannot infer type. Skipping.")
                 continue

            # Find the corresponding definition in the OpenAPI schema
            # Use jsonPath primarily if available and supported
            prop_details = None
            target_path_for_type_inference = None

            if json_path and JSONPATH_SUPPORTED:
                prop_details = _get_openapi_definition_by_path(source_schema, json_path)
                target_path_for_type_inference = json_path
                if not prop_details:
                    log.warning(f"Could not find OpenAPI definition fragment using JSONPath '{json_path}' for attribute '{ldap_attr_name}' in OC '{ldap_oc_name}'. Type inference might be inaccurate.")
            elif openapi_prop_name:
                # Fallback to simple property name lookup
                prop_details = source_schema.get('properties', {}).get(openapi_prop_name)
                target_path_for_type_inference = openapi_prop_name
                if not prop_details:
                    log.warning(f"Could not find OpenAPI property '{openapi_prop_name}' for attribute '{ldap_attr_name}' in OC '{ldap_oc_name}'. Type inference might be inaccurate.")

            # If no details found, make a best guess or default
            if prop_details is None:
                prop_details = {} # Use empty dict to allow defaults

            # Infer type, required status, etc. from the found definition
            attr_type = _infer_attribute_type(prop_details, attr_mapping)
            is_multi_valued = prop_details.get('type') == 'array'
            is_primary_key = False
            is_read_only = None # Will be None unless set by mapping
            # Infer required status from OpenAPI schema first
            is_required = prop_details.get('required', False)

            if attr_mapping:
                # Use details from the mapping file
                is_primary_key = (ldap_attr_name == primary_key_ldap_attr)
                # Mapping can override readOnly and required status
                if 'readOnly' in attr_mapping:
                    is_read_only = attr_mapping['readOnly']
                if 'required' in attr_mapping:
                    is_required = attr_mapping['required']

            attributes.append({
                'ldapName': ldap_attr_name,
                'type': attr_type,
                'primaryKey': is_primary_key,
                'multiValued': is_multi_valued,
                'readOnly': is_read_only, # Include flag (True/False)
                'required': is_required # Include flag
            })

        if not primary_key_ldap_attr or not any(a['primaryKey'] for a in attributes):
            # If primary key was specified in mapping but not found/mapped, treat as error for this OC
            if primary_key_ldap_attr:
                log.error(f"Mapped primary key attribute '{primary_key_ldap_attr}' for object class '{ldap_oc_name}' was not found in the OpenAPI schema properties or its mapping is invalid. Skipping this object class.")
                continue # Skip adding this object class to the context
            else:
                log.warning(f"No primary key attribute was specified or successfully mapped for object class '{ldap_oc_name}'. Operations like search-by-DN might fail.")
                # Continue processing, but be aware operations might be limited

        object_classes.append({
            'ldapName': ldap_oc_name,
            'attributes': attributes
            # Add backend name/resource mapping if needed by template
        })

    return {"object_classes": object_classes}
