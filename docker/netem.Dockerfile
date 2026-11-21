# Linux container for the kernel tc netem validation (scripts/netem_validate.sh)
# on machines without a Linux kernel, e.g. macOS with Docker Desktop.
# Built and run by scripts/netem_docker.sh; see docs/real-network.md.

FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends iproute2 sudo \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so that code changes do not re-download them.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[dev]"

# Bake the tokenizer into the image so token counts use o200k_base, as in
# results/final, instead of the approximate fallback when the download fails.
ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken
RUN python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"

COPY scripts ./scripts

# The container runs as root, so the script's "sudo tc ..." needs no password.
CMD ["scripts/netem_validate.sh"]
