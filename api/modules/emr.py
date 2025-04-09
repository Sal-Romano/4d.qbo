"""
Wrapper module for integrating with the 4D EMR system
"""
import os
import sys
import logging
import importlib.util

# Add scripts directory to path
scripts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts'))
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

# Try to import FourDManager dynamically
try:
    # Try to find the module
    spec = importlib.util.find_spec('scripts.4d_manager')
    if spec is not None:
        # Import the module
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Get the FourDManager class
        FourDManager = module.FourDManager
    else:
        raise ImportError("Could not find module scripts.4d_manager")
except ImportError as e:
    logging.error(f"Failed to import FourDManager: {e}")
    # Create a placeholder class that raises exceptions
    class FourDManager:
        def __init__(self):
            raise ImportError("FourDManager module could not be imported")
        
        def get_patient(self, patient_id):
            raise ImportError("FourDManager module could not be imported") 