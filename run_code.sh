#!/bin/bash

# Copy the user-provided script to the container's working directory
cp $1 /app/temporary_main.py

# Execute the script
python /app/temporary_main.py
