from typing import Dict, Any
import re

# Ensure absolute imports are used
from parsers.openapi_parser import OpenAPISpec
from parsers.mapping_parser import MappingSpec

# --- Configuration Constants ---
# TODO: Make these configurable or discover them if possible
# It's CRITICAL that this SDK version matches the target IDDM v8.1+ environment
# IDDM_SDK_VERSION = "8.1.0-SNAPSHOT" # Placeholder - Now passed as argument
# OKHTTP_VERSION = "4.12.0" # Example version for OkHttp
# JACKSON_VERSION = "2.17.0" # Example version for Jackson
MAVEN_COMPILER_PLUGIN_VERSION = "3.13.0"
MAVEN_SHADE_PLUGIN_VERSION = "3.5.2"
JSONPATH_VERSION = "2.9.0" # Jayway JsonPath
# JAVA_VERSION = "11" # IDDM v8 likely requires Java 11 or 17 - Now passed as argument
# --- End Configuration Constants ---

def _generate_group_id(package_name: str) -> str:
    """Generates a plausible groupId from the package name."""
    parts = package_name.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[:-1]) # e.g., com.example.generated
    elif len(parts) == 1:
        return parts[0] # Use the single part if that's all there is
    else:
        return "com.example.generated" # Default fallback

def _generate_artifact_id(package_name: str, openapi_spec: OpenAPISpec) -> str:
    """Generates a plausible artifactId from package name or OpenAPI title."""
    parts = package_name.split('.')
    if len(parts) >= 1 and parts[-1] != 'connector':
        # Use the last part of the package name if descriptive
        name = parts[-1]
    else:
        # Fallback to OpenAPI title or a generic name
        title = openapi_spec.data.get('info', {}).get('title', 'GenericRestConnector')
        # Sanitize title for use as artifactId (alphanumeric, hyphen, underscore)
        name = re.sub(r'[^a-zA-Z0-9_-]+', '-', title).lower()
        # Remove leading/trailing hyphens
        name = name.strip('-')
        if not name:
             name = "generated-connector"

    # Ensure it ends with -connector for clarity
    if not name.endswith("-connector"):
         name += "-connector"
    return name

def prepare_pom_context(
    openapi_spec: OpenAPISpec,
    mapping_spec: MappingSpec,
    package_name: str,
    sdk_version: str, # Added parameter
    java_version: str, # Added parameter
    okhttp_version: str, # Added parameter
    jackson_version: str # Added parameter
) -> Dict[str, Any]:
    """
    Prepares the context dictionary needed to render the pom.xml template.

    Args:
        openapi_spec: The parsed OpenAPI specification object.
        mapping_spec: The parsed mapping specification object.
        package_name: The base Java package name.
        sdk_version: The target IDDM SDK version.
        java_version: The target Java version.
        okhttp_version: The target OkHttp version.
        jackson_version: The target Jackson version.

    Returns:
        A dictionary containing data for the Jinja2 template.
    """

    group_id = _generate_group_id(package_name)
    artifact_id = _generate_artifact_id(package_name, openapi_spec)
    version = openapi_spec.data.get('info', {}).get('version', '1.0.0') # Use API version if available

    context = {
        'group_id': group_id,
        'artifact_id': artifact_id,
        'version': version,
        'connector_name': openapi_spec.data.get('info', {}).get('title', artifact_id),
        'java_version': java_version, # Use passed argument
        'iddm_sdk_version': sdk_version, # Use passed argument
        'okhttp_version': okhttp_version, # Use passed argument
        'jackson_version': jackson_version, # Use passed argument
        'jsonpath_version': JSONPATH_VERSION,
        'maven_compiler_plugin_version': MAVEN_COMPILER_PLUGIN_VERSION,
        'maven_shade_plugin_version': MAVEN_SHADE_PLUGIN_VERSION,
        # Add other necessary details here
    }
    return context
