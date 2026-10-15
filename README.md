# DuckBot

DuckBot is a Discord bot written in Python using the discord.py library for the CS Club's Discord Server. It provides various commands and functionality to enhance your Discord server experience.

## Getting Started

To get started, please follow these steps:

1. Create a Discord bot application through the developer portal.
   1. Go to the [Discord Applications](https://discord.com/developers/applications) (log in if needed) and create a new application.

   2. Select "New Application" in the top right. Name it, something like "testing".

   3. Enable permissions
      1. On the left, select "Installation"
      2. Scroll down to "Install Link", make sure this is set to "Discord Provided Link" and copy it. We will use this later.
      3. Scroll down to "Default Install Settings" → "Guild Install" → "Scopes"
      4. In "Scopes", "application.commands" should already be selected. Expand the dropdown and select "bot".
      5. Both "application.commands" and "bot" should be selected
      6. Under "Permissions" select "Administrator"
      7. Click Save

   4. Add bot to your Test Server
      1. Make sure to create a Test Server in Discord. This server should be owned by you and have nothing important in it.
      2. In one of the server's chats, paste the "Install Link" we copied earlier in **1.iii.b**.
      3. Click the link and follow the steps
      4. Your bot should now be in your testing server!

   5. Enable intents and copy bot token
      1. On the left, select "Bot"
      2. Scroll to "Token", select "Reset Token", then copy the token. We will use this later.
      3. Scroll to "Privileged Gateway Intents" and enable the following 3 options:
         1. Presence Intent (Enable this)
         2. Server Members Intent (Enable this)
         3. Message Content Intent (Enable this)

2. Fork the repo, clone it and open the project in your IDE of choice.

3. Duplicate the `example.env` and name it `.env`.

4. Open the `.env` and replace `BOT_TOKEN` with your bot's token by pasting it in from **1.v.b**.
   ```
   BOT_TOKEN="HUIHuiHUIHUIH6767HJKjkyuiHBuihuiHUIhuihuihuihHipgA"
   ```

5. Install `uv` if not already installed:

    Linux, macOS, Windows (WSL)
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
    Windows (Powershell)
    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

6. Install dependencies:

    ```sh
    uv sync
    uv run pre-commit install
    ```

7. Run the bot.

    ```bash
    uv run python src/main.py
    ```

## Contributing

We welcome contributions to enhance Duckbot! If you find any issues, have suggestions, or want to request a feature, please follow our [Contributing Guidelines](https://github.com/compsci-adl/.github/blob/main/CONTRIBUTING.md).

## License

This project is licensed under the MIT License.
See [LICENSE](LICENSE) for details.
