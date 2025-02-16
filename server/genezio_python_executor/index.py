from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Response
import os
import sys
import subprocess
import shutil
import urllib.parse
from typing import List
from fastapi.responses import Response
from requests_toolbelt import MultipartEncoder
import mimetypes
from starlette.background import BackgroundTask

app = FastAPI()

UPLOAD_DIR = "/tmp/code_exec"
OUTPUT_DIR = "/tmp/output"

def parse_dependencies(dependencies: str = Query("")) -> List[str]:
    """
    Parse dependencies from the request.
    """
    try:
        decoded_string = urllib.parse.unquote(dependencies)
        if not decoded_string:
            return []
        deps = decoded_string.split(",")
        print(f"Dependencies to install: {deps}")
        return deps
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing dependencies: {str(e)}")

def install_dependencies(dependencies: List[str]):
    """
    Install dependencies to a temporary directory.
    """
    for dep in dependencies:
        print(f"Installing dependency: {dep} using {sys.executable}")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", dep, "--target", "/tmp/deps"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"Error occurred while installing {dep}: {result.stderr}")
        else:
            print(f"Successfully installed {dep}.")

def execute_main():
    """
    Execute the main.py script inside the upload directory.
    """
    main_script_path = os.path.join(UPLOAD_DIR, "main.py")

    if not os.path.exists(main_script_path):
        raise HTTPException(status_code=400, detail="main.py not found. Please upload a valid main.py file.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = "/tmp/deps" + ":" + ":".join(sys.path)
    env["OUTPUT_DIR"] = OUTPUT_DIR

    result = subprocess.run(
        [sys.executable, main_script_path],
        capture_output=True,
        text=True,
        env=env,
        cwd=UPLOAD_DIR  # Ensure scripts run inside the upload directory
    )

    return result.stdout, result.stderr

def create_multipart_response(stdout: str, stderr: str):
    """
    Create a multipart response containing stdout, stderr, and output files.
    """
    fields = {
        "stdout": stdout,
        "stderr": stderr,
    }
    
    if os.path.exists(OUTPUT_DIR):
        for filename in os.listdir(OUTPUT_DIR):
            file_path = os.path.join(OUTPUT_DIR, filename)
            if os.path.isfile(file_path):
                with open(file_path, "rb") as f:
                    fields[filename] = (filename, f.read(), mimetypes.guess_type(filename)[0] or "application/octet-stream")
    
    encoder = MultipartEncoder(fields=fields)
    response = Response(content=encoder.to_string(), media_type=encoder.content_type)
    # async def shutdown_server():
    #     os._exit(0)  # Forcefully exit the process
    # response.background = BackgroundTask(shutdown_server)

    return response

@app.post("/execute")
async def execute(
    dependencies: str = Query(""),
    files: List[UploadFile] = File(...)
):
    """
    Endpoint to execute main.py from uploaded files.
    """
    try:
        # Ensure the upload directory exists
        if os.path.exists(UPLOAD_DIR):
            shutil.rmtree(UPLOAD_DIR)  # Clean previous files
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # Parse dependencies
        deps = parse_dependencies(dependencies)
        install_dependencies(deps)

        # Save uploaded files
        for file in files:
            print(file)
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())

        # Execute main.py
        stdout, stderr = execute_main()

        return create_multipart_response(stdout, stderr)

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing code: {str(e)}")
    finally:
        print("Begin cleanup")
        shutil.rmtree(UPLOAD_DIR)  # Cleanup after execution
        print("Finish cleanup")
