# Base image
FROM python:3.11-slim as base

WORKDIR /app

# Install dependencies
COPY pyproject.toml poetry.lock ./

RUN --mount=type=secret,id=GUILD_ID,target=/run/secrets/GUILD_ID \
    --mount=type=secret,id=BOT_TOKEN,target=/run/secrets/BOT_TOKEN \
    GUILD_ID=$(cat /run/secrets/GUILD_ID) \
    BOT_TOKEN=$(cat /run/secrets/BOT_TOKEN) \
    && echo "Guild ID: $GUILD_ID" \
    && pip install poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-dev

# Copy the rest of the application code
COPY . .

# Run the bot
CMD ["poetry", "run", "python", "src/main.py"]
