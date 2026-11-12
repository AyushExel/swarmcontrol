# SwarmControl: self-hosted image (dashboard + API on one port).
# Build:  docker build -t swarmcontrol .
# Run:    see deploy/docker-compose.yml and tutorials/self-hosted.md

# 1. the dashboard (React), built into the Python package
FROM node:22-bookworm-slim AS web
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY vite.config.ts tsconfig.json ./
COPY web web
RUN npx vite build

# 2. SwarmControl
FROM python:3.12-slim-bookworm
# clang (14 on bookworm): Bend compiles the gates into a native program with it
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl clang \
  && rm -rf /var/lib/apt/lists/*

# Bend proves the laws and runs the gates (the install script fetches the current release and checks its sha256).
# It is required: without it every gated action fails closed.
ENV BEND_HOME=/opt/bend BEND_NO_TELEMETRY=1 PATH=/opt/bend/bin:$PATH
RUN curl -fsSL https://bend-lang.com/install.sh | sh && bend version

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src src
COPY --from=web /build/src/swarmcontrol/web src/swarmcontrol/web
RUN pip install --no-cache-dir . && rm -rf /app/src

RUN useradd --create-home --uid 10001 swarmcontrol && mkdir -p /data && chown swarmcontrol /data
USER swarmcontrol
ENV SWARMCONTROL_DB=/data/swarmcontrol.db SWARMCONTROL_CACHE=/data/cache PORT=8787
VOLUME /data
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fsS -o /dev/null http://127.0.0.1:8787/ || exit 1
# a network address needs SWARMCONTROL_TOKEN (the server refuses to start without one)
CMD ["swctl", "serve", "--host", "0.0.0.0"]
