import json
# from jsonschema import validate # For future validation
from jsonschema import validate, ValidationError

# Basic schema to check for essential top-level OpenAPI keys
# We check for either 'openapi' (v3) or 'swagger' (v2)
# A more complete validation against the official OpenAPI schema could be added later.
OPENAPI_BASIC_SCHEMA = {
    "type": "object",
    "properties": {
        "info": {"type": "object"},
        "paths": {"type": "object"},
        # Optional, but good to check
        "servers": {"type": "array"},
        "components": {"type": "object"},
        "securityDefinitions": {"type": "object"},
        "definitions": {"type": "object"},
        "security": {"type": "array"}
    },
    "required": ["info", "paths"],
    "oneOf": [
        {"required": ["openapi"]},
        {"required": ["swagger"]}
    ]
}

class OpenAPISpec:
    """Represents the parsed OpenAPI specification."""
    def __init__(self, spec_data):
        self.data = spec_data
        # TODO: Add helper methods to easily access parts of the spec
        # e.g., get_servers(), get_security_schemes(), get_paths(), get_schemas()

    def get_servers(self):
        return self.data.get('servers', [])

    def get_security_schemes(self):
        # OpenAPI v2 uses 'securityDefinitions', v3 uses 'components.securitySchemes'
        if 'components' in self.data and 'securitySchemes' in self.data['components']:
            return self.data['components']['securitySchemes']
        elif 'securityDefinitions' in self.data:
            return self.data['securityDefinitions']
        return {}

    def get_paths(self):
        return self.data.get('paths', {})

    def get_schemas(self):
        # OpenAPI v2 uses 'definitions', v3 uses 'components.schemas'
        if 'components' in self.data and 'schemas' in self.data['components']:
            return self.data['components']['schemas']
        elif 'definitions' in self.data:
            return self.data['definitions']
        return {}


def load_openapi_spec(filepath: str) -> OpenAPISpec:
    """Loads, validates (basic structure), and parses the OpenAPI specification from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            spec_data = json.load(f)

        # TODO: Add validation against OpenAPI schema using jsonschema
        # schema_url = "..." # URL or path to the OpenAPI schema definition
        # validate(instance=spec_data, schema=...)
        try:
            validate(instance=spec_data, schema=OPENAPI_BASIC_SCHEMA)
            print("Basic OpenAPI structure validation passed.")
        except ValidationError as e:
            print(f"Error: OpenAPI file format validation failed for {filepath}:")
            print(f"  - {e.message} (Path: {'/'.join(map(str, e.path)) or 'root'})")
            # Optionally print more details from e
            raise ValueError(f"Invalid OpenAPI file format: {e.message}") from e

        return OpenAPISpec(spec_data)
    except FileNotFoundError:
        print(f"Error: OpenAPI file not found at {filepath}")
        raise
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {filepath}")
        raise
    except Exception as e:
        print(f"An unexpected error occurred while loading OpenAPI spec: {e}")
        raise 