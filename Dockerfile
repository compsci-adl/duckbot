# Base image
FROM python:3.11-slim as base

WORKDIR /app

# Install dependencies
COPY pyproject.toml poetry.lock ./

RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev

# Copy the rest of the application code
COPY . .

# Set environment variables during runtime
CMD ["sh", "-c", \
    "GUILD_ID=$(cat /run/secrets/GUILD_ID) && \
    BOT_TOKEN=$(cat /run/secrets/BOT_TOKEN) && \
    poetry run python src/main.py"]
