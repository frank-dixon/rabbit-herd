FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

ARG NODE_VERSION=22.14.0
RUN arch="$(dpkg --print-architecture)" \
    && case "$arch" in \
         amd64) node_arch="x64" ;; \
         arm64) node_arch="arm64" ;; \
         *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
       esac \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.gz" \
      | tar -xz -C /usr/local --strip-components=1 \
    && node --version \
    && npm --version

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY package.json package-lock.json ./
COPY . .

RUN npm ci \
    && npm run build \
    && SECRET_KEY=collectstatic-build-only-not-a-runtime-secret \
       APP_HOSTNAME=build.invalid \
       python manage.py collectstatic --noinput \
    && rm -rf node_modules

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
