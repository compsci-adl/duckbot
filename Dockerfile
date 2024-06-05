# Base image
FROM python:3.11-slim as base

WORKDIR /app

# Install dependencies
COPY pyproject.toml poetry.lock ./

RUN pip install --upgrade pip \
    && pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev

# Copy the rest of the application code
COPY . .

# Environment variables
ENV GUILD_ID=GUILD_ID
ENV BOT_TOKEN=BOT_TOKEN

# Run the bot
CMD ["poetry", "run", "python", "src/main.py"]
