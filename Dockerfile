FROM python:3.13-slim

# Security and runtime defaults.
ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1 \
	PIP_DISABLE_PIP_VERSION_CHECK=1

# Create an unprivileged user and application directory.
RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

WORKDIR /app

# Install only runtime dependencies first to leverage Docker layer caching.
COPY pyproject.toml ./
COPY src ./src

# Install package from source into the container Python environment.
RUN pip install --no-cache-dir .

# Lock down permissions on application files.
RUN chown -R app:app /app

USER app

# This image is intended to be inherited by concrete microservices.
# Downstream images should provide service-specific ENTRYPOINT/CMD.
