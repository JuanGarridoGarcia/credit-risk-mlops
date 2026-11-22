# syntax=docker/dockerfile:1.7
# Application image (decisions A7 and A8, D-025 and D-026).
# Two stages: "builder" installs the locked dependencies with uv; "runtime" copies only
# the resulting environment, so uv, caches and build tools never reach the final image.
# Base images are pinned by version AND digest; Dependabot proposes updates.

ARG PYTHON_IMAGE=python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
ARG UV_IMAGE=astral/uv:0.11.32@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c

FROM ${UV_IMAGE} AS uv

# ---------------------------------------------------------------- builder
FROM ${PYTHON_IMAGE} AS builder

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# 1) Dependencies only: this layer is reused while pyproject.toml and uv.lock do not change.
#    The optional "extra_ca" secret is for networks behind a TLS-inspecting proxy; it is
#    mounted only during this RUN and never stored in a layer (see docs/errors.md, E-008).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=secret,id=extra_ca \
    if [ -f /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-dev --no-install-project

# 2) The project itself, installed as a regular (non-editable) package, as in production.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=extra_ca \
    if [ -f /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------- test
# Unit tests against the project installed as a regular package, not the editable
# install used for development (decision A3): catches files missing from the package.
# Built only on demand (`make test-image`, CI); never shipped.
FROM builder AS test

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=extra_ca \
    if [ -f /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-editable --group dev

COPY tests ./tests
ENV PATH="/opt/venv/bin:${PATH}"
RUN rm -rf /app/src
USER nobody
CMD ["pytest", "tests/unit", "-p", "no:cacheprovider"]

# ---------------------------------------------------------------- runtime
FROM ${PYTHON_IMAGE} AS runtime

LABEL org.opencontainers.image.title="credit-risk" \
      org.opencontainers.image.source="https://github.com/JuanGarridoGarcia/credit-risk-mlops"

# Unprivileged user with a fixed id (test B5).
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder --chown=app:app /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
USER app

CMD ["credit-risk"]
