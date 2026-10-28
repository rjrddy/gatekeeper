FROM rust:1.99.1-bookworm AS agent
WORKDIR /build
COPY agent/ ./
RUN cargo build --release --locked

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.13-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 GK_AGENT=/app/bin/gatekeeper-agent GK_WEB=/app/apps/web/dist GK_DATABASE=/data/gatekeeper.db
RUN groupadd --gid 10001 gatekeeper && useradd --uid 10001 --gid 10001 --create-home gatekeeper && mkdir /data && chown gatekeeper:gatekeeper /data
COPY pyproject.toml ./
COPY gatekeeper/ ./gatekeeper/
COPY fixtures/ ./fixtures/
RUN pip install --no-cache-dir --upgrade pip==26.2.2 setuptools==84.1.0 && pip install --no-cache-dir .
COPY --from=agent /build/target/release/gatekeeper-agent /app/bin/gatekeeper-agent
COPY --from=web /web/dist /app/apps/web/dist
COPY deploy/logging.json /app/deploy/logging.json
USER gatekeeper
EXPOSE 8080
CMD ["uvicorn", "gatekeeper.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080", "--log-config", "deploy/logging.json"]
