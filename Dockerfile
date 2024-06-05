# Base image
FROM python:3.11-slim as base

WORKDIR /app

# Install dependencies
COPY pyproject.toml poetry.lock ./

RUN pip install poetry \
    && poetry install --without dev

# Copy the rest of the application code
COPY . .

# Run the bot
CMD ["poetry", "run", "python", "src/main.py"]
