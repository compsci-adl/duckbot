# Base image
FROM python:3.11-slim AS base

WORKDIR /app

# Install dependencies
COPY pyproject.toml poetry.lock ./

RUN pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy the rest of the application code
COPY . .

# Run the bot
CMD ["poetry", "run", "python", "src/main.py"]
