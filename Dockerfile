# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
# We use --no-cache-dir to keep the image small
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project files
# (The .dockerignore file will exclude unnecessary items)
COPY . .

# Expose the port the app runs on
EXPOSE 5050

# Define environment variable to ensure output is logged
ENV PYTHONUNBUFFERED=1

# Command to run the application
# We use the simplified app.py we just created
CMD ["python", "src/app.py"]
