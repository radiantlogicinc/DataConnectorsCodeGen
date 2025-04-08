import subprocess
import json
import os
import shutil
import sys

# --- Configuration ---
TEST_CASES_FILE = "./tests/smoke_test/test_cases.json"
PACKAGE_DIR = "dataconnectors_codegen" 
# Module path for -m execution - points to the package
GENERATOR_MODULE_PATH = "dataconnectors_codegen"
BASE_OUTPUT_DIR = "./tests/smoke_test/generated_connectors"
PYTHON_EXECUTABLE = sys.executable 
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PACKAGE_ROOT_DIR = os.path.join(PROJECT_ROOT, "dataconnectors_codegen") # Path to the package itself
# ---

def run_smoke_tests():
    """Reads test cases and runs the generator for each."""
    print("--- Starting Smoke Tests ---")

    # Check existence based on __main__.py within the package
    generator_entry_point_check = os.path.join(PROJECT_ROOT, PACKAGE_DIR, '__main__.py')
    if not os.path.exists(generator_entry_point_check):
        print(f"ERROR: Generator entry point not found at {generator_entry_point_check}")
        print(f"Hint: Ensure {PACKAGE_DIR}/__main__.py exists.")
        return False

    test_cases_abs_path = os.path.join(PROJECT_ROOT, TEST_CASES_FILE)
    if not os.path.exists(test_cases_abs_path):
        print(f"ERROR: Test cases file not found at {test_cases_abs_path}")
        return False

    try:
        with open(test_cases_abs_path, 'r') as f:
            test_cases = json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load test cases from {test_cases_abs_path}: {e}")
        return False

    base_output_abs_path = os.path.join(PROJECT_ROOT, BASE_OUTPUT_DIR)
    # Ensure base output directory exists and is clean
    if os.path.exists(base_output_abs_path):
        print(f"Cleaning existing output directory: {base_output_abs_path}")
        shutil.rmtree(base_output_abs_path)
    os.makedirs(base_output_abs_path)
    print(f"Created base output directory: {base_output_abs_path}")

    all_passed = True
    for case in test_cases:
        case_id = case.get("case_id", "unknown_case")
        description = case.get("description", "No description")
        # Keep paths relative for the command-line args, check absolute below
        openapi_path_rel = case.get("openapi") # e.g., "./tests/smoke_test/inputs/minimal_openapi.json"
        mapping_path_rel = case.get("mapping") # e.g., "./tests/smoke_test/inputs/minimal_mapping.json"
        extra_args = case.get("extra_args", [])
        output_dir_rel = os.path.join(BASE_OUTPUT_DIR, case_id) # Relative path for output arg

        print(f"\n--- Running Test Case: {case_id} ---")
        print(f"Description: {description}")

        if not openapi_path_rel or not mapping_path_rel:
            print("ERROR: Test case missing 'openapi' or 'mapping' path.")
            all_passed = False
            continue

        # Check existence using paths relative to project root
        openapi_path_abs = os.path.join(PROJECT_ROOT, openapi_path_rel)
        mapping_path_abs = os.path.join(PROJECT_ROOT, mapping_path_rel)

        if not os.path.exists(openapi_path_abs):
            print(f"ERROR: OpenAPI input file not found at resolved path: {openapi_path_abs}")
            all_passed = False
            continue

        if not os.path.exists(mapping_path_abs):
             print(f"ERROR: Mapping input file not found at resolved path: {mapping_path_abs}")
             all_passed = False
             continue

        # Construct command to execute main.py directly
        command = [PYTHON_EXECUTABLE, os.path.join(PACKAGE_ROOT_DIR), 
                   '--openapi', openapi_path_rel,
                   '--mapping', mapping_path_rel,
                   '--output', output_dir_rel,
                   '--no-build'] + extra_args

        print(f"Running command: {' '.join(command)}")

        # Prepare environment: Add the PACKAGE directory to PYTHONPATH
        run_env = os.environ.copy()
        pythonpath = run_env.get('PYTHONPATH', '')
        # Add the directory containing parsers/, generator/ etc. to the path
        run_env['PYTHONPATH'] = f"{PACKAGE_ROOT_DIR}{os.pathsep}{pythonpath}" 
        print(f"DEBUG: Setting PYTHONPATH for subprocess to: {run_env['PYTHONPATH']}")

        try:
            # Run the generator script directly with modified env and CWD=PROJECT_ROOT
            result = subprocess.run(command,
                                    capture_output=True,
                                    text=True,
                                    check=False,
                                    env=run_env, 
                                    cwd=PROJECT_ROOT 
                                    )
            
            # ---- ALWAYS PRINT OUTPUT ----
            print("--- Subprocess STDOUT: ---")
            print(result.stdout)
            print("--- Subprocess STDERR: ---")
            print(result.stderr)
            print("-------------------------")
            # ---- END PRINT OUTPUT ----

            output_dir_abs_check = os.path.abspath(output_dir_rel)

            if result.returncode == 0:
                print(f"SUCCESS: Test case {case_id} completed.")
                # print("Output:\n", result.stdout) # Optionally print stdout
                if not os.path.exists(output_dir_abs_check):
                     print(f"WARNING: Test case {case_id} succeeded but output directory {output_dir_abs_check} not found!")
                     # all_passed = False # Consider if this should be a failure
                elif not os.path.exists(os.path.join(output_dir_abs_check, 'pom.xml')):
                     print(f"WARNING: Test case {case_id} succeeded but pom.xml not found in {output_dir_abs_check}")

            else:
                print(f"FAILURE: Test case {case_id} failed with return code {result.returncode}.")
                # Stderr/Stdout are already printed above
                all_passed = False

        except Exception as e:
            print(f"ERROR: Exception occurred while running test case {case_id}: {e}")
            all_passed = False

    print("\n--- Smoke Tests Finished ---")
    if all_passed:
        print("Result: All smoke tests PASSED.")
        return True
    else:
        print("Result: Some smoke tests FAILED.")
        return False

if __name__ == "__main__":
    if run_smoke_tests():
        sys.exit(0)
    else:
        sys.exit(1)