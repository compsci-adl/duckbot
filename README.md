# DuckBot

DuckBot is a Discord bot written in Python using the discord.py library for the CS Club's Discord Server. It provides various commands and functionality to enhance your Discord server experience.

## Getting Started

To get started, please follow these steps:

1. Install Poetry and add it to your PATH if not already installed:

    Linux, macOS, Windows (WSL)
    ```bash
    curl -sSL https://install.python-poetry.org | python3 -
    export PATH="$HOME/.local/bin:$PATH"
    ```
    Windows (Powershell)
    ```powershell
    (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
    setx PATH "%APPDATA%\Python\Scripts;%PATH%"
    ```

2. Install the dependencies.

    ```bash
    poetry install
    ```

3. Copy `.env.example` to a new file `.env` and set required environment variables.

4. Navigate to the src directory

    ```bash
    cd src
    ```

5. Run the bot.

    ```bash
    poetry run python main.py
    ```

## Contributing

We welcome contributions to enhance Duckbot! If you find any issues, have suggestions, or want to request a feature, please follow our [Contributing Guidelines](https://github.com/compsci-adl/.github/blob/main/CONTRIBUTING.md).

## License

This project is licensed under the MIT License.
See [LICENSE](LICENSE) for details.
