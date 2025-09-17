
FROM node:18-alpine AS web-builder

WORKDIR /app/web

# Copy package files
COPY web/package.json web/package-lock.json* ./

# Install dependencies
RUN npm ci

# Copy source code
COPY web/ ./

# Build the React app
RUN npm run build

FROM python:3.13-slim-bookworm AS reqs

WORKDIR /app

RUN pip install --no-cache-dir poetry poetry-plugin-export

COPY ./pyproject.toml ./poetry.lock /app/

RUN poetry export --without-hashes -f requirements.txt --output requirements.txt

FROM python:3.13-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000

WORKDIR /app


RUN --mount=type=bind,from=reqs,source=/app/requirements.txt,target=/app/requirements.txt \
    pip install --no-cache-dir -r requirements.txt && \
    apt update && \
    apt install -y curl git && \
    apt-get clean autoclean && \
    apt-get autoremove --yes && \
    rm -rf /var/lib/{apt,dpkg,cache,log}

COPY src/ .

# Copy built React app from web-builder stage
COPY --from=web-builder /app/web/dist ./static

EXPOSE 8000

# HEALTHCHECK \
#     --interval=15s \
#     --timeout=10s \
#     --start-period=15s \
#     CMD curl -fs http://localhost:5000/healthcheck

USER 1000:1000

ENTRYPOINT [ "uvicorn", "server:api" ]
