import os
import shutil
from flask import Flask
from flask_frozen import Freezer
from app import app  # Import your Flask app

# Create build directory if it doesn't exist
BUILD_DIR = 'build'
if os.path.exists(BUILD_DIR):
    shutil.rmtree(BUILD_DIR)
os.makedirs(BUILD_DIR)

# Initialize Frozen-Flask
freezer = Freezer(app)

if __name__ == '__main__':
    # Generate static files
    freezer.freeze()
    
    # Copy static assets
    shutil.copytree('static', os.path.join(BUILD_DIR, 'static'), dirs_exist_ok=True)
    
    print("Build completed! Files are in the 'build' directory.")
