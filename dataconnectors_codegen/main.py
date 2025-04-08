import click
import os
import traceback
import sys

# **** ADD PRINT HERE ****
print("DEBUG: Loading dataconnectors_codegen/main.py module")

# Ensure absolute imports are used
# Assuming execution from project root or package structure is handled correctly
try:
    from .parsers.openapi_parser import load_openapi_spec
    from .parsers.mapping_parser import load_mapping_spec
    from .generator.engine import GeneratorEngine
except ImportError:
    # Fallback for direct script execution or different environment setup
    from parsers.openapi_parser import load_openapi_spec
    from parsers.mapping_parser import load_mapping_spec
    from generator.engine import GeneratorEngine
print("DEBUG: Imported parsers and engine in main.py") # DEBUG

# --- Core Logic Function (undecorated) ---
def run_generation(openapi: str, mapping: str, output: str, package_name: str, sdk_version: str, java_version: str, schema_extraction: bool, okhttp_version: str, jackson_version: str, no_build: bool):
    """Contains the actual generation logic."""
    print("DEBUG: Entered run_generation function")
    
    click.echo("Starting connector generation...")
    click.echo(f"  OpenAPI Spec: {openapi}")
    click.echo(f"  Mapping Spec: {mapping}")
    click.echo(f"  Output Dir:   {output}")
    click.echo(f"  Package Name: {package_name}")
    click.echo(f"  SDK Version:  {sdk_version}")
    click.echo(f"  Java Version: {java_version}")
    click.echo(f"  Schema Extraction Enabled: {schema_extraction}")
    click.echo(f"  OkHttp Version: {okhttp_version}")
    click.echo(f"  Jackson Version: {jackson_version}")

    # 1. Load and Parse Inputs
    click.echo("Loading specifications...")
    openapi_spec = load_openapi_spec(openapi)
    mapping_spec = load_mapping_spec(mapping)
    click.echo("Specifications loaded successfully.")

    # 2. Prepare Output Directory
    if not os.path.exists(output):
        os.makedirs(output)
        click.echo(f"Created output directory: {output}")
    else:
        click.echo(f"Output directory exists: {output}")
        # Consider adding an overwrite confirmation/option here

    # 3. Initialize Generator Engine
    print("DEBUG: About to init GeneratorEngine")
    engine = GeneratorEngine(
        openapi_spec,
        mapping_spec,
        output,
        package_name,
        sdk_version,
        java_version,
        schema_extraction,
        okhttp_version,
        jackson_version
    )
    print("DEBUG: GeneratorEngine initialized")

    # 4. Run Generation Process
    print("DEBUG: About to call engine.generate_all()")
    engine.generate_all()
    print("DEBUG: Returned from engine.generate_all()")

    click.echo("Connector generation finished successfully!")
    click.echo(f"Generated project located at: {os.path.abspath(output)}")

    # Optional: Offer to run mvn package?
    # Skip if --no-build flag is set
    if not no_build:
        run_build = click.confirm('\nDo you want to attempt to build the connector JAR using Maven? (Requires Maven in PATH)', default=False)
        if run_build:
            engine.build_connector()
    else:
        click.echo("Skipping Maven build step as requested by --no-build flag.")

# --- Click Command Wrapper ---
@click.command()
@click.option('--openapi', '-o', required=True, type=click.Path(exists=True, dir_okay=False), help='Path to the OpenAPI specification file (JSON).')
@click.option('--mapping', '-m', required=True, type=click.Path(exists=True, dir_okay=False), help='Path to the mapping specification file (JSON).')
@click.option('--output', '-out', default='./generated_connector', type=click.Path(file_okay=False), help='Output directory for the generated connector project.')
@click.option('--package-name', '-p', default='com.example.generated.connector', help='Java package name for the generated code.')
@click.option('--sdk-version', '-sv', default='8.1.0', help='Target IDDM SDK version (e.g., 8.1.0).')
@click.option('--java-version', '-jv', default='11', help='Target Java version (e.g., 11 or 17).')
@click.option('--schema-extraction', '-se', is_flag=True, default=False, help='Enable generation of SchemaExtractionOperations.')
@click.option('--okhttp-version', '-okv', default='4.12.0', help='OkHttp version to use.')
@click.option('--jackson-version', '-jsv', default='2.17.0', help='Jackson version to use.')
@click.option('--no-build', is_flag=True, default=False, help='Skip the Maven build step after generation.')
def generate_command(openapi: str, mapping: str, output: str, package_name: str, sdk_version: str, java_version: str, schema_extraction: bool, okhttp_version: str, jackson_version: str, no_build: bool):
    """Generates an IDDM Data Connector from an OpenAPI spec and a mapping file."""
    print("DEBUG: Entered generate_command (click wrapper)") # NEW DEBUG
    # Call the core logic function
    run_generation(
        openapi, mapping, output, package_name, sdk_version, java_version,
        schema_extraction, okhttp_version, jackson_version, no_build
    )

# --- Script Execution Entry Point ---
# When running `python dataconnectors_codegen/main.py ...`,
# Click automatically handles invoking the decorated `generate_command`.
# We no longer need an explicit call or `if __name__ == '__main__'` here
# for the script execution path used by the test runner.

# print("DEBUG: Reached end of main.py, calling generate() unconditionally.")
# generate_command() # We don't call this directly anymore