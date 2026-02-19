import livekit
import livekit.agents
import pkgutil
import importlib
import os
import sys

def search_for_classes(class_names):
    print(f"Searching for {class_names} in LiveKit packages...")
    
    # Get all possible livekit paths
    paths = set()
    try:
        paths.update(livekit.__path__)
    except: pass
    try:
        paths.update(livekit.agents.__path__)
    except: pass
    
    print(f"Search paths: {paths}")
    
    found_any = False
    for path in paths:
        for loader, module_name, is_pkg in pkgutil.walk_packages([path], 'livekit.'):
            # If it's rtc, skip most to save time unless it's direct
            if '.rtc.' in module_name and not module_name.endswith('.rtc'):
                continue
                
            try:
                module = importlib.import_module(module_name)
                for class_name in class_names:
                    if hasattr(module, class_name):
                        print(f"🏆 FOUND: from {module_name} import {class_name}")
                        print(f"   Location: {module.__file__}")
                        found_any = True
            except Exception:
                continue
    return found_any

if __name__ == "__main__":
    print("-" * 50)
    print("SEARCHING FOR ANY 'Agent' CLASSES IN livekit.agents")
    print("-" * 50)
    
    for loader, module_name, is_pkg in pkgutil.walk_packages(livekit.agents.__path__, 'livekit.agents.'):
        try:
            module = importlib.import_module(module_name)
            for name in dir(module):
                if "Agent" in name:
                    # Filter out some common ones to avoid noise
                    if name in ["AgentEvent", "AgentTask", "AgentServer", "AgentSession", "AgentHandoff"]:
                        continue
                    print(f"FOUND: from {module_name} import {name}")
                    # Attempt to get the full path if it's a class/object, otherwise just print the name
                    try:
                        obj = getattr(module, name)
                        if isinstance(obj, type): # Check if it's a class
                            print(f"   Full path: {obj.__module__}.{obj.__name__}")
                        else:
                            print(f"   Full path: {module_name}.{name}")
                    except AttributeError:
                        print(f"   Full path: {module_name}.{name}")
        except Exception:
            continue
