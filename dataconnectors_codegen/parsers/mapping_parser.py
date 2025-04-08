import json
# from jsonschema import validate # For future validation
from jsonschema import validate, ValidationError

# Schema definition for the mapping file
MAPPING_SCHEMA = {
    "type": "object",
    "properties": {
        "dnStructure": {
            "type": "object",
            "properties": {
                "baseDnSuffix": {"type": "string"},
                "rdnAttribute": {"type": "string"},
                "components": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "ldapName": {"type": "string"},
                            "openApiParameterName": {"type": "string"}
                        },
                        "required": ["ldapName", "openApiParameterName"]
                    }
                }
            },
            "required": ["baseDnSuffix", "rdnAttribute"]
        },
        "objectClasses": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "ldapName": {"type": "string"},
                    "openApiSchemaRef": {"type": "string"},
                    "openApiSchemaName": {"type": "string"},
                    "apiEndpoint": {"type": "string"}, # Path template, e.g., /users/{userId}
                    "primaryKeyLdapAttribute": {"type": "string"},
                    "primaryKeyOpenApiParameterName": {"type": "string"}, # e.g., userId from path
                    "primaryKeyJsonPath": {"type": "string"}, # Optional: for getting key from response body
                    "attributes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "ldapName": {"type": "string"},
                                "openApiPropertyName": {"type": "string"},
                                "jsonPath": {"type": "string"},
                                "typeOverride": {"type": "string"},
                                "readOnly": {"type": "boolean"},
                                "required": {"type": "boolean"},
                                "apiQueryParam": {"type": "string"} # For mapping LDAP filter attribute to API query param
                            },
                            "required": ["ldapName"],
                            "oneOf": [
                                {"required": ["openApiPropertyName"]},
                                {"required": ["jsonPath"]}
                            ]
                        }
                    }
                },
                "required": ["ldapName", "attributes"],
                 "oneOf": [
                    {"required": ["openApiSchemaRef"]},
                    {"required": ["openApiSchemaName"]}
                 ]
            }
        }
    },
    "required": ["dnStructure", "objectClasses"]
}

class MappingSpec:
    """Represents the parsed Mapping specification."""
    def __init__(self, mapping_data):
        self.data = mapping_data
        # TODO: Define the expected structure based on mapping file definition
        # TODO: Add helper methods to easily access mappings, e.g.,
        # get_object_class_map(ldap_oc)
        # get_attribute_map(ldap_oc, ldap_attr)
        # get_dn_structure()
        # get_rest_resource_for_oc(ldap_oc)

    # Placeholder methods - structure assumed
    def get_ldap_object_classes(self):
        """Returns a list of defined LDAP object classes."""
        return list(self.data.get('objectClasses', {}).keys())

    def get_object_class_mapping(self, ldap_oc: str):
        """Returns the mapping details for a specific LDAP object class."""
        return self.data.get('objectClasses', {}).get(ldap_oc)

    def get_dn_structure(self):
        """Returns the defined DN structure mapping."""
        return self.data.get('dnStructure')

def load_mapping_spec(filepath: str) -> MappingSpec:
    """Loads, validates, and parses the Mapping specification from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)

        # TODO: Add validation against the defined Mapping schema using jsonschema
        # mapping_schema = { ... } # Define the expected schema
        # validate(instance=mapping_data, schema=mapping_schema)
        try:
            validate(instance=mapping_data, schema=MAPPING_SCHEMA)
            print("Mapping file validation passed.")
        except ValidationError as e:
            print(f"Error: Mapping file format validation failed for {filepath}:")
            print(f"  - {e.message} (Path: {'/'.join(map(str, e.path)) or 'root'})")
            raise ValueError(f"Invalid mapping file format: {e.message}") from e

        return MappingSpec(mapping_data)
    except FileNotFoundError:
        print(f"Error: Mapping file not found at {filepath}")
        raise
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred while loading mapping spec: {e}")
        raise 