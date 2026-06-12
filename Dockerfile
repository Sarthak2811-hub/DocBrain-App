# Use Lightweight python base image
FROM python:3.11-slim

# set environment variable to optimize python running inside Docker 
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# set working directory in container
WORKDIR /code

# Install system dependencies 
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# copy requirements file and install python packages
COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

# copy application code  to container
COPY . /code/

# expose the port uvicorn runs on
EXPOSE 8000

# Run uvicorn binding 0.0.0.0 so it accessible outside container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]