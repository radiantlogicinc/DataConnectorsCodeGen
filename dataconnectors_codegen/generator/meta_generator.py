import re
from typing import List, Dict, Any, Optional

# Ensure absolute imports are used
from parsers.openapi_parser import OpenAPISpec

def _to_camel_case(snake_str: str) -> str:
    """Converts snake_case or kebab-case to camelCase."""
    parts = re.split('_|-', snake_str)
    # Ensure parts[0] exists and handle potential empty strings if split yields them unexpectedly
    first_part = parts[0] if parts else ''
    other_parts = [x.title() for x in parts[1:] if x] # Ensure parts are not empty
    return first_part + "".join(other_parts)

def _format_label(name: str) -> str:
    """Creates a human-readable label from a variable name."""
    # Replace underscores/hyphens with spaces
    s = re.sub("[_|-]+", " ", name)
    # Add space before caps in camelCase (if not preceded by a space or start of string)
    s = re.sub(r"(?<!\s)(?<!^)(?=[A-Z])", " ", s)
    return s.title()

def prepare_meta_context(
    openapi_spec: OpenAPISpec,
    connector_name: Optional[str] = None,
    generate_schema_extraction: bool = False
) -> Dict[str, Any]:
    """
    Prepares the context dictionary needed to render the meta.json template.

    Args:
        openapi_spec: The parsed OpenAPI specification object.
        connector_name: An optional name for the connector template.
        generate_schema_extraction: Flag indicating if schema extraction is supported.

    Returns:
        A dictionary containing data for the Jinja2 template.
    """
    properties = []
    processed_security_schemes = set()

    # 1. Handle Servers - Define Base URL property
    servers = openapi_spec.get_servers()
    default_url_value = ''
    base_url_desc = "Base URL of the target API (e.g., https://api.example.com/v1)."

    if servers:
        # Use the first server URL as the default, allow override
        first_server = servers[0]
        default_url_value = first_server.get('url', '')
        variables = first_server.get('variables', {})
        base_url_desc = "Base URL of the target API."
        if variables:
            # Construct an example URL with default variable values
            example_url = default_url_value
            for var_name, var_details in variables.items():
                # Replace {var} with its default value in the example
                example_url = example_url.replace(f'{{{var_name}}}', var_details.get('default', f'<{var_name}>'))
            base_url_desc += f" Example: {example_url}"
            # The default value for the input field should be the template URL itself
        else:
            base_url_desc += f" Example: {default_url_value}"

    properties.append({
        'name': 'baseUrl',
        'label': 'API Base URL',
        'type': 'text',
        'required': True,
        'description': base_url_desc,
        'default': default_url_value # Use the potentially variable-containing URL as default
    })


    # 2. Handle Security Schemes
    security_schemes = openapi_spec.get_security_schemes()
    # Check global security requirements (OpenAPI v3)
    global_security = openapi_spec.data.get('security', [])
    required_schemes = set()
    if global_security:
        for req in global_security:
            required_schemes.update(req.keys())

    for name, scheme in security_schemes.items():
        if name in processed_security_schemes:
            continue

        scheme_type = scheme.get('type')
        required = name in required_schemes
        # Use original scheme name for generating property names initially
        prop_base_name = _to_camel_case(name)

        if scheme_type == 'apiKey':
            api_key_name = scheme.get('name') # Header/query param name
            api_key_in = scheme.get('in')     # 'header' or 'query'
            # Prefer real key name for label/description if available
            prop_name_final = _to_camel_case(api_key_name if api_key_name else name)
            prop_label = _format_label(api_key_name if api_key_name else name)
            prop_desc = f"API Key for authentication (sent as '{api_key_name}' in {api_key_in})."
            if scheme.get('description'):
                prop_desc += f" {scheme.get('description')}"

            properties.append({
                'name': f'{prop_name_final}ApiKey',
                'label': f'{prop_label} API Key',
                'type': 'password', # Use password type for masking
                'required': required,
                'description': prop_desc.strip()
            })
            processed_security_schemes.add(name)

        elif scheme_type == 'http':
            http_scheme = scheme.get('scheme') # 'basic', 'bearer', etc.
            prop_label_base = _format_label(name)
            prop_desc_base = scheme.get('description', '')

            if http_scheme == 'basic':
                properties.append({
                    'name': 'httpUsername',
                    'label': 'HTTP Basic Username',
                    'type': 'text',
                    'required': required,
                    'description': f"Username for HTTP Basic authentication. {prop_desc_base}".strip()
                })
                properties.append({
                    'name': 'httpPassword',
                    'label': 'HTTP Basic Password',
                    'type': 'password',
                    'required': required,
                    'description': "Password for HTTP Basic authentication."
                })
                processed_security_schemes.add(name)
            elif http_scheme == 'bearer':
                 properties.append({
                    'name': f'{prop_base_name}BearerToken',
                    'label': f'{prop_label_base} Bearer Token',
                    'type': 'password',
                    'required': required,
                    'description': f"Bearer token for authentication. {prop_desc_base}".strip()
                })
                 processed_security_schemes.add(name)
            # TODO: Add other HTTP schemes if needed (e.g., digest)

        elif scheme_type == 'oauth2':
            # OAuth2 is complex. Generate basic properties for common flows.
            flows = scheme.get('flows', {})
            # Get first defined flow (e.g., 'authorizationCode', 'clientCredentials')
            # We might need more logic if multiple flows are defined
            flow_type, flow_details = next(iter(flows.items()), (None, {}))
            prop_label_base = _format_label(name)
            prop_desc_base = scheme.get('description', '')

            # Common properties (might not apply to all flows)
            properties.append({
                'name': f'{prop_base_name}ClientId',
                'label': f'{prop_label_base} OAuth Client ID',
                'type': 'text',
                'required': True, # Usually required
                'description': f"Client ID for OAuth2 flow. {prop_desc_base}".strip()
            })
            # Client secret is not used in implicit or PKCE-enhanced auth code flows
            # Let's assume it's required for simplicity unless specific flow indicates otherwise
            client_secret_required = flow_type not in ['implicit'] # Add other flows if needed
            properties.append({
                'name': f'{prop_base_name}ClientSecret',
                'label': f'{prop_label_base} OAuth Client Secret',
                'type': 'password',
                'required': client_secret_required,
                'description': "Client Secret for OAuth2 flow."
            })

            # Flow-specific properties
            auth_url = flow_details.get('authorizationUrl')
            token_url = flow_details.get('tokenUrl')
            scopes = flow_details.get('scopes') # This is a dictionary {scope_name: description}

            if auth_url:
                 properties.append({
                    'name': f'{prop_base_name}AuthorizationUrl',
                    'label': f'{prop_label_base} OAuth Authorization URL',
                    'type': 'text',
                    'required': flow_type in ['authorizationCode', 'implicit'], # Required for user interaction flows
                    'default': auth_url,
                    'description': "OAuth2 Authorization Endpoint URL."
                 })
            if token_url:
                 properties.append({
                    'name': f'{prop_base_name}TokenUrl',
                    'label': f'{prop_label_base} OAuth Token URL',
                    'type': 'text',
                    'required': flow_type in ['authorizationCode', 'clientCredentials', 'password'], # Flows that exchange something for a token
                    'default': token_url,
                    'description': "OAuth2 Token Endpoint URL."
                 })
            if scopes:
                 scope_string = ', '.join(scopes.keys())
                 properties.append({
                    'name': f'{prop_base_name}Scopes',
                    'label': f'{prop_label_base} OAuth Scopes',
                    'type': 'text', # Simple text input for scopes
                    'required': False,
                    'description': f"OAuth2 scopes required (comma-separated). Available: {scope_string}"
                 })

            processed_security_schemes.add(name)

        # TODO: Handle openIdConnect, mutualTLS etc. if needed

    # Use info.title as default connector name if not provided
    # Default to 'Generated REST Connector' if title is missing
    info_block = openapi_spec.data.get('info', {})
    final_connector_name = connector_name or info_block.get('title', 'Generated REST Connector')

    context = {
        'connector_name': final_connector_name,
        'category': 'Custom', # Default category
        'schema_extractable': generate_schema_extraction,
        'properties': properties,
        'multiple_accounts_supported': False # Default to false, could be configurable
    }
    return context
