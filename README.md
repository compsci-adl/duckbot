# DuckBot

DuckBot is a Discord bot written in Python using the discord.py library for the CS Club's Discord Server. It provides various commands and functionality to enhance your Discord server experience.

## Getting Started

To get started, please follow these steps:

1. Install `uv` if not already installed:

    Linux, macOS, Windows (WSL)
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
    Windows (Powershell)
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

2. Install dependencies:

    ```sh
    uv sync
    uv run pre-commit install
    ```

3. Copy `.env.example` to a new file `.env` and set required environment variables.

4. Run the bot.

    ```bash
    uv run python src/main.py
    ```

## Contributing

We welcome contributions to enhance Duckbot! If you find any issues, have suggestions, or want to request a feature, please follow our [Contributing Guidelines](https://github.com/compsci-adl/.github/blob/main/CONTRIBUTING.md).

## License

This project is licensed under the MIT License.
See [LICENSE](LICENSE) for details.
