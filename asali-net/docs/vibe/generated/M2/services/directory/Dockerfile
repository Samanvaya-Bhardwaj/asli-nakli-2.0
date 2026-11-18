# Build from asali-net/: docker build -f services/directory/Dockerfile -t asali-directory .
FROM python:3.11-slim
RUN useradd --create-home --uid 10001 asali && mkdir /data && chown asali /data
COPY services/directory /src/directory
RUN pip install --no-cache-dir /src/directory
USER asali
ENV DATA_DIR=/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/directory/v1/health')"
CMD ["uvicorn", "asali_directory.main:app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000"]
