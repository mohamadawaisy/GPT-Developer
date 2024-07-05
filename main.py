from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from dependencies import save_data, load_data, save_requirements, load_requirements, install_packages, run_script, CODE_FILE, REQUIREMENTS_FILE
from fastapi import Query
import os
import subprocess
app = FastAPI()

class Function(BaseModel):
    name: str
    code: str

class Requirement(BaseModel):
    package_name: str

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

@app.post('/functions/bulk/')
def manage_multiple_functions(functions: List[Function]):
    existing_functions = load_data(CODE_FILE)
    function_dict = {func['name']: func['code'] for func in existing_functions}

    for function in functions:
        function_dict[function.name] = function.code  # Updates or adds new function

    save_data(CODE_FILE, list(map(lambda name: {'name': name, 'code': function_dict[name]}, function_dict.keys())))
    return {"status": "success", "message": "Functions updated successfully."}

@app.get('/functions/')
def get_function(name: str):
    functions = load_data(CODE_FILE)
    for func in functions:
        if func['name'] == name:
            return func
    raise HTTPException(status_code=404, detail="Function not found")

@app.get('/functions/multiple/')
def get_multiple_functions(names: List[str]):
    functions = load_data(CODE_FILE)
    result = [func for func in functions if func['name'] in names]
    if not result:
        raise HTTPException(status_code=404, detail="One or more functions not found")
    return result

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

@app.post('/requirements/install/')
def install_requirements():
    success, message = install_packages()
    return {"status": "success" if success else "error", "message": message}

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

    # File path
    script_file_path = "temporary_main.py"

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

    # Execute the script file
    try:
        result = subprocess.run(['python', script_file_path], text=True, capture_output=True, check=True, timeout=5)
        return {"status": "success", "output": result.stdout}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="The process timed out.")
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute script: {e}")
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
