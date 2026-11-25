# syntax=docker/dockerfile:1.7
# Application images (decisions A7 and A8, D-025 and D-026; two images since D-078).
# Builder stages install the locked dependencies with uv; the final stages copy only the
# resulting environment, so uv, caches and build tools never reach a shipped image.
#   serve  the package with what predicting needs (scikit-learn, LightGBM, mlflow-skinny)
#   train  serve plus the "train" dependency group (Optuna, full MLflow, SHAP); it also
#          runs the MLflow tracking server of docker compose
# Both come from the same uv.lock, so a model trained in one loads in the other (test B8).
# Base images are pinned by version AND digest; Dependabot proposes updates.

ARG PYTHON_IMAGE=python:3.12.16-slim-trixie@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b
ARG UV_IMAGE=astral/uv:0.13.9@sha256:d3b601f0c7b118bc1753febf7c41cc80981df678445e0254284eecf84db79a7d

FROM ${UV_IMAGE} AS uv

# ---------------------------------------------------------------- builder (serve)
FROM ${PYTHON_IMAGE} AS builder

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# 1) Dependencies only: this layer is reused while pyproject.toml and uv.lock do not change.
#    --no-default-groups: only the project's own dependencies, none of the groups.
#    The optional "extra_ca" secret is for networks behind a TLS-inspecting proxy; it is
#    mounted only during this RUN and never stored in a layer (see docs/errors.md, E-008).
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=secret,id=extra_ca \
    if [ -f /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-default-groups --no-install-project

# 2) The project itself, installed as a regular (non-editable) package, as in production.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=extra_ca \
    if [ -f /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-default-groups --no-editable

# ---------------------------------------------------------------- builder (train)
FROM builder AS builder-train

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=extra_ca \
    if [ -f /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-default-groups --group train --no-editable

# ---------------------------------------------------------------- builder (test)
FROM builder-train AS builder-test

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=secret,id=extra_ca \
    if [ -f /run/secrets/extra_ca ]; then export SSL_CERT_FILE=/run/secrets/extra_ca; fi; \
    uv sync --frozen --no-editable --no-default-groups --group train --group dev

# ---------------------------------------------------------------- runtime base
FROM ${PYTHON_IMAGE} AS runtime

LABEL org.opencontainers.image.title="credit-risk" \
      org.opencontainers.image.source="https://github.com/JuanGarridoGarcia/credit-risk-mlops"

# LightGBM needs the OpenMP runtime (D-072), which the slim image does not carry.
# Behind a TLS-inspecting proxy that only tunnels HTTPS (the "extra_ca" secret, E-008),
# apt goes over HTTPS with that CA for this RUN only; the sources are restored after.
# The CA is mounted readable by all: apt downloads as its own unprivileged user (_apt).
# It is a public certificate, not a secret; it is mounted outside /run/secrets because
# this step stays in the history of the shipped images, which B5 scans for secret words.
RUN --mount=type=secret,id=extra_ca,mode=0444,target=/run/extra_ca.pem \
    set -e; sources=/etc/apt/sources.list.d/debian.sources; opts=""; \
    if [ -f /run/extra_ca.pem ]; then \
        sed -i 's|http://deb.debian.org|https://deb.debian.org|' "$sources"; \
        opts="-o Acquire::https::CAInfo=/run/extra_ca.pem -o Acquire::https::Proxy=${https_proxy:-false}"; \
    fi; \
    apt-get $opts update; \
    apt-get $opts install --yes --no-install-recommends libgomp1; \
    sed -i 's|https://deb.debian.org|http://deb.debian.org|' "$sources"; \
    rm -rf /var/lib/apt/lists/*

# Unprivileged user with a fixed id (test B5).
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
USER app
CMD ["credit-risk"]

# ---------------------------------------------------------------- test
# Unit tests against the project installed as a regular package, not the editable
# install used for development (decision A3): catches files missing from the package.
# Built on the runtime base, so the tests see the system libraries of the shipped images
# (LightGBM needs libgomp1). Built only on demand (`make test-image`, CI); never shipped.
FROM runtime AS test
COPY --from=builder-test /opt/venv /opt/venv
COPY pyproject.toml ./
COPY tests ./tests
COPY reports/data_audit/data_dictionary.csv ./reports/data_audit/data_dictionary.csv
COPY docs/validation_rules.md docs/tests.md ./docs/
# The delivery tooling and the workflows, read by T22.1 and T22.2 (E-049); never shipped.
COPY ci ./ci
COPY .github/workflows ./.github/workflows
# Prefect writes its settings folder at import; the test user has no home (E-041).
ENV MPLCONFIGDIR=/tmp/matplotlib \
    PREFECT_HOME=/tmp/prefect
USER nobody
CMD ["pytest", "tests/unit", "-p", "no:cacheprovider"]

# ---------------------------------------------------------------- train
FROM runtime AS train
LABEL org.opencontainers.image.title="credit-risk-train"
# Where the MLflow server keeps artefacts and the flow writes its data (named volumes take
# the owner of these folders, so the unprivileged user can write to them).
USER root
RUN mkdir -p /mlflow/artifacts /app/data && chown -R app:app /mlflow /app/data
USER app
# The commit of the code, recorded with every training set and model (D-079); the key of
# a training (D-101). `make build` and CI pass it; without it, training stops with an error.
ARG CREDIT_RISK_COMMIT=""
# Prefect writes its settings folder at import; the app user has no home (E-041).
ENV CREDIT_RISK_COMMIT=${CREDIT_RISK_COMMIT} \
    PREFECT_HOME=/tmp/prefect
COPY --from=builder-train --chown=app:app /opt/venv /opt/venv

# ---------------------------------------------------------------- serve (default target)
FROM runtime AS serve
LABEL org.opencontainers.image.title="credit-risk-serve"
COPY --from=builder --chown=app:app /opt/venv /opt/venv
