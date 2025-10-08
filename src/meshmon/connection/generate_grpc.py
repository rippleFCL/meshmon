#!/usr/bin/env python3
"""
Generate gRPC Python files from proto definitions.
Run this script when the proto files change.
"""

import subprocess
import sys
from pathlib import Path


def generate_grpc_code():
    connection_dir = Path(__file__).parent
    proto_dir = connection_dir / "proto"
    proto_file = connection_dir / "meshmon.proto"

    if not proto_file.exists():
        print(f"Proto file not found: {proto_file}")
        sys.exit(1)

    for folder, _, files in proto_dir.walk():
        for file in files:
            if file != "__init__.py" and file.endswith((".py", ".pyi")):
                try:
                    (folder / file).unlink()
                except Exception as e:
                    print(f"Failed to delete {file}: {e}")

    proto_dir.mkdir(parents=True, exist_ok=True)
    # Generate Python gRPC code
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"--proto_path={connection_dir}",
        f"--python_out={proto_dir}",
        f"--grpc_python_out={proto_dir}",
        f"--mypy_out={proto_dir}",
        str(proto_file),
    ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        # Fix the import in the generated gRPC file to use relative import
        grpc_file = proto_dir / "meshmon_pb2_grpc.py"
        if grpc_file.exists():
            content = grpc_file.read_text()
            content = content.replace(
                "import meshmon_pb2 as meshmon__pb2",
                "from . import meshmon_pb2 as meshmon__pb2",
            )
            grpc_file.write_text(content)

        print("gRPC code generated successfully!")
        print(f"Generated files in: {proto_dir}")

    except subprocess.CalledProcessError as e:
        print(f"Error generating gRPC code: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    generate_grpc_code()
