import os
import importlib
from fastapi import FastAPI, APIRouter
import logging
import pkgutil
import inspect

def discover_routers(app: FastAPI, api_prefix: str = "/api.v1", package_name: str = "api.v1"):
    """
    Discovers and registers all routers in the specified package
    
    Args:
        app: FastAPI application instance
        api_prefix: Prefix for all API endpoints
        package_name: Root package to start router discovery
    """
    print(f"Discovering routers in {package_name}...")
    logging.info(f"Discovering routers in {package_name}...")
    
    # Import the package (api.v1)
    package = importlib.import_module(package_name)
    
    # Get the file system path of the package
    package_path = os.path.dirname(package.__file__)
    
    # Register main endpoints.py in v1 package if it exists
    if hasattr(package, "endpoints") and hasattr(package.endpoints, "router"):
        print(f"Mounting main endpoints router from {package_name}.endpoints at {api_prefix}")
        logging.info(f"Mounting main endpoints router from {package_name}.endpoints")
        app.include_router(package.endpoints.router, prefix=api_prefix)
    
    # Recursively discover routers in all subpackages (like 4demr)
    discovered = pkgutil.walk_packages(path=[package_path], prefix=f"{package_name}.")
    
    for _, module_name, is_pkg in discovered:
        if not is_pkg:  # If it's a module (not a package)
            try:
                module = importlib.import_module(module_name)
                
                # Look for router objects in the module
                for attr_name, attr_value in inspect.getmembers(module):
                    if isinstance(attr_value, APIRouter):
                        # Include the router with the API prefix
                        router_path = module_name.replace(package_name, "")
                        # Remove the trailing .py if it exists
                        if router_path.endswith(".py"):
                            router_path = router_path[:-3]
                        
                        # Get just the directory part for the router prefix
                        # For example, from ".4demr.get_patient" get ".4demr"
                        last_dot = router_path.rfind('.')
                        if last_dot != -1:
                            # Get the directory part
                            dir_path = router_path[:last_dot]
                            # Convert dots to slashes
                            dir_path = dir_path.replace(".", "/")
                            url_path = f"{api_prefix}{dir_path}"
                        else:
                            # No directory part, e.g., ".endpoints"
                            # Convert dots to slashes
                            dir_path = router_path.replace(".", "/")
                            url_path = f"{api_prefix}{dir_path}"
                        
                        print(f"Mounting router from {module_name} at {url_path}")
                        logging.info(f"Mounting router from {module_name} at {url_path}")
                        
                        # Show registered routes on the router
                        print(f"Routes on this router:")
                        for route in attr_value.routes:
                            full_path = f"{url_path}{route.path}"
                            print(f"  - {', '.join(route.methods)} {full_path}")
                        
                        app.include_router(attr_value, prefix=url_path)
            except Exception as e:
                error_msg = f"Error importing module {module_name}: {e}"
                print(error_msg)
                logging.error(error_msg)
    
    print("Router discovery complete")
    logging.info("Router discovery complete") 