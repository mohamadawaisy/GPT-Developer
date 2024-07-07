from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
from dependencies import save_data, load_data, save_requirements, load_requirements, install_packages, run_script, CODE_FILE, REQUIREMENTS_FILE
from fastapi import Query
import os
import docker
import json
import uuid
import datetime

app = FastAPI()
client = docker.from_env()

class Function(BaseModel):
    name: str
    code: str

class Requirement(BaseModel):
    package_name: str

def create_session_folder():
    session_id = str(uuid.uuid4())
    folder_path = os.path.join("logs", session_id)
    os.makedirs(folder_path, exist_ok=True)
    return session_id, folder_path

async def log_request_response(request: Request, call_next):
    session_id = request.headers.get('Session-Id')
    if not session_id:
        session_id, folder_path = create_session_folder()
    else:
        folder_path = os.path.join("logs", session_id)

    request_data = {
        "method": request.method,
        "url": str(request.url),
        "headers": dict(request.headers),
        "body": await request.body()
    }
    request_log_path = os.path.join(folder_path, f"{datetime.datetime.now().isoformat()}_request.json")
    with open(request_log_path, 'w') as f:
        json.dump(request_data, f, default=str)

    response = await call_next(request)
    
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    response_data = {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": response_body.decode('utf-8')
    }
    response_log_path = os.path.join(folder_path, f"{datetime.datetime.now().isoformat()}_response.json")
    with open(response_log_path, 'w') as f:
        json.dump(response_data, f, default=str)

    return JSONResponse(content=json.loads(response_body), status_code=response.status_code, headers=dict(response.headers))

app.middleware('http')(log_request_response)

@app.post('/functions/')
@app.put('/functions/')
def manage_functions(function: Function):
    functions = load_data(CODE_FILE)
    updated = False
    for i, func in enumerate(functions):
        if func['name'] == function.name:
            functions[i]['code'] = function.code
            updated = True
            break
    if not updated:
        functions.append(function.dict())  # Append to the list
    save_data(CODE_FILE, functions)
    return {"status": "success", "message": f"Function {function.name} {'updated' if updated else 'added'} successfully."}

@app.get('/functions/')
def get_function(name: str):
    functions = load_data(CODE_FILE)
    for func in functions:
        if func['name'] == name:
            return func
    raise HTTPException(status_code=404, detail="Function not found")

@app.post('/requirements/add/')
def add_requirement(requirement: Requirement):
    packages = load_requirements()
    if requirement.package_name not in packages:
        packages.append(requirement.package_name)
        save_requirements(packages)
        return {"status": "success", "message": f"Package {requirement.package_name} added successfully."}
    return {"status": "error", "message": "Package already in list."}

@app.post('/requirements/bulk/')
def add_multiple_requirements(requirements: List[Requirement]):
    existing_packages = load_requirements()
    package_dict = {pkg: True for pkg in existing_packages}

    for req in requirements:
        package_dict[req.package_name] = True  # This will simply overwrite if already exists

    save_requirements(list(package_dict.keys()))
    return {"status": "success", "message": "Packages updated successfully."}

@app.post('/requirements/remove/')
def remove_requirement(requirement: Requirement):
    packages = load_requirements()
    if requirement.package_name in packages:
        packages.remove(requirement.package_name)
        save_requirements(packages)
        return {"status": "success", "message": f"Package {requirement.package_name} removed successfully."}
    return {"status": "error", "message": "Package not found in list."}

@app.get('/requirements/')
def list_requirements():
    packages = load_requirements()
    return {"packages": packages}

@app.post('/run-main/')
def run_main():
    # Load all functions from the data file
    functions = load_data(CODE_FILE)

    # If there are no functions, return an error
    if not functions:
        raise HTTPException(status_code=404, detail="No functions found")

    # Extract the 'main' function if it exists
    main_func = next((func for func in functions if func['name'] == 'main'), None)
    if not main_func:
        raise HTTPException(status_code=404, detail="Main function not found")

    # Create the code to be executed by concatenating all function definitions
    full_code = '\n'.join(func['code'] for func in functions)  # This ensures all dependent functions are also included

    # File paths
    script_file_path = "temporary_main.py"
    requirements_file_path = "requirements.txt"
    open(requirements_file_path, 'a').close()
    # Ensure file does not exist before writing (optional but clarifies intention)
    if os.path.exists(script_file_path):
        try:
            os.remove(script_file_path)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Error removing old script file: {e}")

    # Write the complete code to a new temporary script file
    try:
        with open(script_file_path, "w") as file:
            file.write(full_code)
    except IOError as e:
        raise HTTPException(status_code=500, detail=f"Failed to write to script file: {e}")

    # Ensure the requirements file exists
    if not os.path.exists(requirements_file_path):
        raise HTTPException(status_code=404, detail="requirements.txt file not found")

    # Run the script in a Docker container
    try:
        container = client.containers.run(
            image="my_python_sandbox",
            command=[
                "/bin/bash", 
                "-c", 
                f"pip install -r /app/{requirements_file_path} && python /app/{script_file_path}"
            ],
            volumes={
                os.path.abspath(script_file_path): {
                    'bind': f'/app/{script_file_path}',
                    'mode': 'ro'
                },
                os.path.abspath(requirements_file_path): {
                    'bind': f'/app/{requirements_file_path}',
                    'mode': 'ro'
                }
            },
            remove=True,
            stdout=True,
            stderr=True
        )
        output = container.decode("utf-8")
        return {"status": "success", "output": output}
    except docker.errors.ContainerError as e:
        raise HTTPException(status_code=500, detail=f"Container error: {e.stderr.decode('utf-8')}")
    except docker.errors.DockerException as e:
        raise HTTPException(status_code=500, detail=f"Docker error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post('/functions/multiple/')
def get_multiple_functions(names: List[str] = Query(...)):
    functions = load_data(CODE_FILE)
    result = [func for func in functions if func['name'] in names]
    if not result:
        raise HTTPException(status_code=404, detail="One or more functions not found")
    return result

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8000)
