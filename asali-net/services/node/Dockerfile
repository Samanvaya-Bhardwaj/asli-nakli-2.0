# Build from asali-net/: docker build -f services/node/Dockerfile -t asali-node .
FROM node:22-alpine AS web
WORKDIR /web
COPY apps/portal-web/package.json apps/portal-web/package-lock.json ./
RUN npm ci
COPY apps/portal-web ./
RUN npm run build

FROM python:3.11-slim
RUN useradd --create-home --uid 10001 asali && mkdir /data && chown asali /data
COPY packages /src/packages
COPY services/node /src/node
RUN pip install --no-cache-dir /src/packages/asali_codes /src/packages/asali_text /src/node
COPY --from=web /web/dist /app/static
COPY ml/models /app/ml/models
USER asali
ENV DATA_DIR=/data ML_MODELS_DIR=/app/ml/models WEB_DIR=/app/static
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/share/v1/health')"
CMD ["uvicorn", "asali_node.main:app_from_env", "--factory", "--host", "0.0.0.0", "--port", "8000"]
