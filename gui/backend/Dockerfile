FROM python:3.11-slim

# Note: this base image does NOT include R. FlowSOM/DepecheR clustering
# require R (+ those Bioconductor packages) installed separately -- either
# extend this Dockerfile, or install them in a running container and
# commit/persist the image. See ../README.md.

WORKDIR /app

# git is needed because requirements.txt installs conclave via a git+https URL
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV CONCLAVE_GUI_DATA=/data
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
