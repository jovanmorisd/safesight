# Optional: run the whole app (API + built React site) as one container on any Docker host.
# Same lightweight runtime as Vercel: ONNX models with onnxruntime, no PyTorch.
# Configuration comes from environment variables (see backend/.env.example).

FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN useradd -m -u 1000 app
WORKDIR /app/backend
COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt
COPY backend/app ./app
COPY backend/ppe_core ./ppe_core
COPY backend/config.yaml ./
COPY backend/models/*.onnx ./models/
COPY --from=web /web/dist /app/frontend/dist
ENV PPE_DATA_DIR=/data HOME=/home/app PORT=8000
RUN mkdir -p /data models/uploads && chown -R app:app /app /data
USER app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
