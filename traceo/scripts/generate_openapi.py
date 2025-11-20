#!/usr/bin/env python3
"""
Generate OpenAPI/Swagger documentation from FastAPI application.

This script extracts the OpenAPI schema from the running Traceo API
and generates documentation in various formats.

Usage:
    python scripts/generate_openapi.py --format json
    python scripts/generate_openapi.py --format yaml --output docs/api.yaml
"""

import json
import sys
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None  # Optional dependency

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.main import app


def generate_openapi_json(output_path: Optional[Path] = None) -> dict:
    """Generate OpenAPI schema in JSON format.

    Args:
        output_path: Optional file path to save JSON schema

    Returns:
        OpenAPI schema dictionary
    """
    openapi_schema = app.openapi()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(openapi_schema, f, indent=2)
        print(f"✓ OpenAPI JSON schema saved to: {output_path}")

    return openapi_schema


def generate_openapi_yaml(output_path: Path) -> str:
    """Generate OpenAPI schema in YAML format.

    Args:
        output_path: File path to save YAML schema

    Returns:
        YAML string

    Raises:
        ImportError: If PyYAML is not installed
    """
    if yaml is None:
        raise ImportError(
            "PyYAML is required to generate YAML format. "
            "Install with: pip install pyyaml"
        )

    openapi_schema = app.openapi()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        yaml.dump(openapi_schema, f, default_flow_style=False, sort_keys=False)

    print(f"✓ OpenAPI YAML schema saved to: {output_path}")
    return yaml.dump(openapi_schema)


def generate_markdown_docs(output_path: Optional[Path] = None) -> str:
    """Generate API documentation in Markdown format.

    Args:
        output_path: Optional file path to save Markdown docs

    Returns:
        Markdown documentation string
    """
    openapi = app.openapi()
    info = openapi.get("info", {})
    paths = openapi.get("paths", {})

    # Start with info section
    md = f"""# {info.get('title', 'Traceo API')} Documentation

{info.get('description', 'REST API for Traceo phishing detection system')}

**Version**: {info.get('version', '1.0.0')}

## Base URL

```
{openapi.get('servers', [{}])[0].get('url', 'http://localhost:8000')}
```

## Table of Contents

"""

    # Generate table of contents
    for path, methods in sorted(paths.items()):
        for method in methods.keys():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                md += f"- [{method.upper()} {path}](#{method.lower()}-{path.replace('/', '-')})\n"

    md += "\n## Endpoints\n\n"

    # Generate detailed endpoint documentation
    for path, methods in sorted(paths.items()):
        for method, details in sorted(methods.items()):
            if method.upper() not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                continue

            method_upper = method.upper()
            summary = details.get("summary", "")
            description = details.get("description", "")

            md += f"### {method_upper} {path}\n\n"
            if summary:
                md += f"**Summary**: {summary}\n\n"
            if description:
                md += f"**Description**:\n\n{description}\n\n"

            # Parameters
            parameters = details.get("parameters", [])
            if parameters:
                md += "**Parameters**:\n\n"
                for param in parameters:
                    param_name = param.get("name", "")
                    param_in = param.get("in", "")
                    param_desc = param.get("description", "")
                    param_required = param.get("required", False)
                    md += f"- **{param_name}** ({param_in})"
                    if param_required:
                        md += " *required*"
                    if param_desc:
                        md += f": {param_desc}"
                    md += "\n"
                md += "\n"

            # Request body
            request_body = details.get("requestBody", {})
            if request_body:
                md += "**Request Body**:\n\n"
                md += "```json\n"
                md += json.dumps(
                    request_body.get("content", {}).get("application/json", {}),
                    indent=2
                ) + "\n"
                md += "```\n\n"

            # Responses
            responses = details.get("responses", {})
            if responses:
                md += "**Responses**:\n\n"
                for status, response in responses.items():
                    md += f"- **{status}**: {response.get('description', 'Response')}\n"
                md += "\n"

            md += "---\n\n"

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(md)
        print(f"✓ Markdown documentation saved to: {output_path}")

    return md


def main():
    """Main entry point for documentation generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate API documentation from Traceo FastAPI application"
    )
    parser.add_argument(
        "--format",
        choices=["json", "yaml", "markdown", "all"],
        default="json",
        help="Documentation format to generate (default: json)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path (auto-determined if not specified)"
    )
    parser.add_argument(
        "--output-dir",
        "-d",
        type=Path,
        default=Path(__file__).parent.parent / "docs" / "api",
        help="Output directory for generated files (default: docs/api)"
    )

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.format == "json" or args.format == "all":
            output_file = args.output or args.output_dir / "openapi.json"
            generate_openapi_json(output_file)

        if args.format == "yaml" or args.format == "all":
            if yaml is None:
                print("⚠ YAML format requires PyYAML. Install with: pip install pyyaml")
            else:
                output_file = args.output or args.output_dir / "openapi.yaml"
                generate_openapi_yaml(output_file)

        if args.format == "markdown" or args.format == "all":
            output_file = args.output or args.output_dir / "API.md"
            generate_markdown_docs(output_file)

        if args.format == "all":
            print("\n✓ All documentation formats generated successfully!")

    except Exception as e:
        print(f"✗ Error generating documentation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
