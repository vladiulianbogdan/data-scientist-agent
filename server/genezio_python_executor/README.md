# Genezio Python Executor

## Overview

This repository provides a FastAPI-based service that enables remote execution of Python scripts with optional dependency installation. Users can upload their Python files and execute `main.py` in a sandboxed environment.

## Features

- **Remote Code Execution**: Upload and execute Python scripts in a controlled environment.
- **Dependency Management**: Automatically install specified Python dependencies before execution.
- **File-Based Input/Output**: Supports file uploads and returns execution results, including standard output, errors, and generated files.
- **Security**: Runs in an isolated `/tmp` directory with automatic cleanup after execution.
- **Multipart Response**: Returns execution results and output files in a multipart response format.

## Deployment

Deploy your own instance of this executor using Genezio:

[![Deploy to Genezio](https://raw.githubusercontent.com/Genez-io/graphics/main/svg/deploy-button.svg)](https://app.genez.io/start/deploy?repository=https://github.com/vladiulianbogdan/genezio-python-executor)

## API Usage

### Endpoint: `/execute`

- **Method**: `POST`
- **Description**: Accepts Python files and executes `main.py` in an isolated environment.

### Request Parameters

| Parameter       | Type             | Description |
|----------------|-----------------|-------------|
| `dependencies` | `string (query)` | Comma-separated list of Python packages to install. Default is empty. |
| `files`        | `multipart/form-data` | One or more Python files (including `main.py`). |

### Example Request

```sh
curl -X POST "http://localhost:8000/execute?dependencies=requests,numpy" \
    -F "files=@main.py" \
    -F "files=@helper.py"
```

### Example Response

The response is a `multipart/form-data` containing:
- **stdout**: Standard output of the script.
- **stderr**: Standard error output.
- **Generated Files** (if any) from the script execution.

#### Example Response Content:

```json
{
  "stdout": "Execution completed successfully.\n",
  "stderr": "",
  "output.txt": "This is the generated file content."
}
```

## Implementation Details

1. **Dependency Installation**
   - Dependencies are parsed from the query string and installed using `pip` into `/tmp/deps`.
   - The `PYTHONPATH` is updated to include `/tmp/deps` before executing the script.

2. **File Handling**
   - Uploaded files are stored in `/tmp/code_exec`.
   - The script `main.py` must be present, or execution will fail.

3. **Execution Flow**
   - Uploaded files are saved.
   - Dependencies (if any) are installed.
   - `main.py` is executed within the `/tmp/code_exec` directory.
   - The output is captured and returned in a multipart response.
   - The `/tmp/code_exec` directory is cleaned up after execution.

## Security Considerations

- The execution environment is cleaned after every request.
- Runs in an isolated directory to prevent conflicts.
- Ensure trusted code execution to avoid malicious scripts.

## License

This project is licensed under the MIT License.

