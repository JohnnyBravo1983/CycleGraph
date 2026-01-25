# ---------- BUILDER: build cyclegraph_core wheel ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Build deps + tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Install Rust (needed for PyO3/maturin build)
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH=/usr/local/cargo/bin:$PATH

RUN curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable

# Install maturin (builder-only)
RUN python -m pip install --upgrade pip && python -m pip install "maturin>=1.4,<2.0"

# Copy only core first (better cache)
COPY core/ /app/core/

# Build wheel
RUN maturin build --release -m /app/core/pyproject.toml -o /tmp/wheels

# ---------- RUNTIME: app ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime deps (keep minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
  && rm -rf /var/lib/apt/lists/*

# Install python deps first (cache)
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && python -m pip install -r /app/requirements.txt

# Install the built cyclegraph_core wheel
COPY --from=builder /tmp/wheels /tmp/wheels
RUN python -m pip install /tmp/wheels/*.whl && rm -rf /tmp/wheels

# Copy rest of repo
COPY . /app

ENV API_HOST=0.0.0.0
ENV API_PORT=8080

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
