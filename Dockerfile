# Use the official Python image from the Docker Hub
FROM python:3.12.4

# Set the working directory inside the container
WORKDIR /app

# Copy requirements file and install any dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main app script
COPY temporary_main.py .

# Command to keep the container running
CMD ["tail", "-f", "/dev/null"]
