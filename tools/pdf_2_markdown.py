from llama_parse import LlamaParse

# Initialize the LlamaParse parser
parser = LlamaParse(
    api_key="llx-9o9TqFkuAhuyUUQ98EX2mHzVHCl7GzreMvDfoH4VXwOBBBbm",  # can also be set in your env as LLAMA_CLOUD_API_KEY
    result_type="markdown",  # "markdown" and "text" are available
    verbose=True
)

# Define parsing instructions for a document
parsing_instruction = """
The provided document is a quarterly report filed by Uber Technologies, Inc. with the Securities and Exchange Commission (SEC).
This form provides detailed financial information about the company's performance for a specific quarter.
It includes unaudited financial statements, management discussion and analysis, and other relevant disclosures required by the SEC.
It contains many tables.
Try to be precise while answering the questions.
"""

# Parse the document
parsed_documents = parser.load_data("./docs/IDDM Connector SDK Public API Design.pdf")

# Save the parsed results
with open('./docs/iddm_connector_sdk_public_api_design.md', 'w') as f:
    for doc in parsed_documents:
        f.write(doc.text + '\n')