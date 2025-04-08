import os
import shutil
import subprocess
import logging
from jinja2 import Environment, FileSystemLoader, select_autoescape
import json
import traceback
import sys

# Import parsers and specific generators
from parsers.openapi_parser import OpenAPISpec
from parsers.mapping_parser import MappingSpec
print("DEBUG: Imported parsers in engine.py") # DEBUG

# Import generator modules (will be created later)
from generator.meta_generator import prepare_meta_context
from generator.schema_generator import prepare_schema_context
from generator.pom_generator import prepare_pom_context
from generator.java_generator import generate_all_java_files
print("DEBUG: Imported sub-generators in engine.py") # DEBUG

log = logging.getLogger(__name__)

class GeneratorEngine:
    """Orchestrates the data connector generation process."""

    def __init__(self, openapi_spec: OpenAPISpec, mapping_spec: MappingSpec, output_dir: str, package_name: str, sdk_version: str, java_version: str, schema_extraction: bool, okhttp_version: str, jackson_version: str):
        print("DEBUG: Entered GeneratorEngine.__init__")
        
        self.openapi_spec = openapi_spec
        self.mapping_spec = mapping_spec
        self.output_dir = output_dir
        self.package_name = package_name
        self.sdk_version = sdk_version
        self.java_version = java_version
        self.generate_schema_extraction = schema_extraction
        self.okhttp_version = okhttp_version
        self.jackson_version = jackson_version
        self.package_path = package_name.replace('.', '/')

        # Configure Jinja2 environment
        self.template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(enabled_extensions=('html', 'xml', 'j2'), default_for_string=True),
            trim_blocks=True,
            lstrip_blocks=True
        )

        # Define output paths within the generated project
        self.base_output_path = os.path.abspath(output_dir)
        self.src_main_java_path = os.path.join(self.base_output_path, 'src', 'main', 'java')
        self.src_main_resources_path = os.path.join(self.base_output_path, 'src', 'main', 'resources')
        self.meta_inf_connector_path = os.path.join(self.src_main_resources_path, 'META-INF', 'connector')
        self.java_package_path = os.path.join(self.src_main_java_path, self.package_path)


    def _create_output_dirs(self):
        """Creates the necessary Maven directory structure."""
        os.makedirs(self.java_package_path, exist_ok=True)
        # Directories for specific code components (client, converter, model)
        os.makedirs(os.path.join(self.java_package_path, 'client'), exist_ok=True)
        os.makedirs(os.path.join(self.java_package_path, 'converter'), exist_ok=True)
        os.makedirs(os.path.join(self.java_package_path, 'model'), exist_ok=True)

        os.makedirs(self.meta_inf_connector_path, exist_ok=True)
        print(f"Created directory structure under: {self.base_output_path}")

    def _render_template(self, template_name: str, context: dict, output_path: str):
        """Renders a Jinja2 template and writes it to the output path."""
        print(f"DEBUG: Attempting to render template '{template_name}' to '{output_path}'")
        
        try:
            template = self.jinja_env.get_template(template_name)
            rendered_content = template.render(context)
            
            if not rendered_content.strip():
                 print(f"WARNING: Template {template_name} rendered empty content!")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(rendered_content)
            print(f"Generated: {output_path}")
        except Exception as e:
             print(f"ERROR rendering template {template_name} or writing to {output_path}: {e}")
             traceback.print_exc()
             # Explicitly exit with error code
             sys.exit(1)

    def generate_all(self):
        """Runs all generation steps."""
        self._create_output_dirs()

        print("\nGenerating pom.xml...")
        self._generate_pom_xml()

        print("\nGenerating meta.json...")
        self._generate_meta_json()

        print("\nGenerating schema definition...")
        self._generate_schema()

        print("\nGenerating Java source code...")
        self._generate_java_code()

        print("\nWriting mapping config resource...")
        self._write_mapping_config()

        # TODO: Copy any static resources if needed

    def _generate_pom_xml(self):
        """Generates the pom.xml file."""
        try:
            context = prepare_pom_context(
                self.openapi_spec,
                self.mapping_spec,
                self.package_name,
                self.sdk_version,
                self.java_version,
                self.okhttp_version,
                self.jackson_version
            )
            output_file_path = os.path.join(self.base_output_path, 'pom.xml')
            self._render_template('resources/pom.xml.j2', context, output_file_path)
        except Exception as e:
            print(f"  Error generating pom.xml: {e}")
            # Optionally re-raise or handle more gracefully

    def _generate_meta_json(self):
        """Generates the meta.json file."""
        try:
            context = prepare_meta_context(
                self.openapi_spec,
                generate_schema_extraction=self.generate_schema_extraction
            )
            output_file_path = os.path.join(self.meta_inf_connector_path, 'meta.json')
            self._render_template('resources/meta.json.j2', context, output_file_path)
        except Exception as e:
            print(f"  Error generating meta.json: {e}")
            # Optionally re-raise or handle more gracefully

    def _generate_schema(self):
        """Generates the schema definition file (.orx)."""
        try:
            context = prepare_schema_context(self.openapi_spec, self.mapping_spec)
            output_file_path = os.path.join(self.meta_inf_connector_path, 'schema.orx')
            self._render_template('resources/schema.orx.j2', context, output_file_path)
        except Exception as e:
            print(f"  Error generating schema.orx: {e}")
            # Optionally re-raise or handle more gracefully

    def _generate_java_code(self):
        """Generates all necessary Java source files."""
        print("DEBUG: Entering _generate_java_code")
        
        generate_all_java_files(
            openapi_spec=self.openapi_spec,
            mapping_spec=self.mapping_spec,
            package_name=self.package_name,
            java_package_base_path=self.java_package_path,
            render_template=self._render_template,
            schema_extraction_enabled=self.generate_schema_extraction
        )
        
        print("DEBUG: Exiting _generate_java_code normally")

    def _write_mapping_config(self):
        """Writes the mapping specification data to a JSON file in resources."""
        output_file_path = os.path.join(self.src_main_resources_path, 'mapping_config.json')
        try:
            with open(output_file_path, 'w', encoding='utf-8') as f:
                # The mapping_spec object holds the raw data dictionary
                json.dump(self.mapping_spec.data, f, indent=2, ensure_ascii=False)
            print(f"Generated: {output_file_path}")
        except Exception as e:
            print(f"  Error writing mapping_config.json: {e}")

    def build_connector(self):
        """(Optional) Attempts to build the generated connector using Maven."""
        log.info("Attempting to build connector JAR using Maven...")
        pom_path = os.path.join(self.base_output_path, 'pom.xml')
        if not os.path.exists(pom_path):
            log.error("Cannot build: pom.xml not found at {}", pom_path)
            return False

        # Simple command execution
        # TODO: Make Maven path configurable? Add error checking based on return code.
        command = ["mvn", "clean", "package", "-f", pom_path]
        log.info(f"Executing Maven command: {' '.join(command)} in {self.base_output_path}")

        try:
            # Use shell=True on Windows if mvn is in PATH but not found directly?
            # Or ensure mvn.cmd is used.
            # Using shell=False is generally safer if mvn is directly executable.
            process = subprocess.run(
                command,
                cwd=self.base_output_path,
                capture_output=True,
                text=True,
                check=False, # Check manually based on returncode
                shell=True if os.name == 'nt' else False # Use shell=True on Windows for mvn.cmd
            )

            if process.returncode == 0:
                log.info("Maven build successful.")
                print("\n--- Maven Build Output ---")
                print(process.stdout)
                print("--------------------------")
                # TODO: Try to find the generated JAR path based on pom artifactId/version
                # final_name = ... # Extract from pom or shade plugin config
                # jar_path = os.path.join(self.base_output_path, 'target', f"{final_name}.jar")
                print(f"Connector JAR should be located in: {os.path.join(self.base_output_path, 'target')}")
                return True
            else:
                log.error("Maven build failed! Return code: {}", process.returncode)
                print("\n--- Maven Build Error Output ---")
                print(process.stderr)
                print(process.stdout) # Also print stdout for context
                print("------------------------------")
                return False

        except FileNotFoundError:
            log.error("Maven command ('mvn') not found. Is Maven installed and in your system PATH?")
            print("Error: 'mvn' command not found. Please ensure Apache Maven is installed and configured in your PATH.")
            return False
        except Exception as e:
            log.error("An unexpected error occurred during Maven build: {}", e)
            print(f"An unexpected error occurred during build: {e}")
            return False 