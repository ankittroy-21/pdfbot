# Telegram PDF Bot

A Telegram bot that converts images to PDF files instantly.

## Features

- Convert images to PDF files on command
- Reply with the generated PDF file with custom filename
- Simple start command to interact with the bot

## Requirements

- Python 3.7+
- Telegram API ID and API Hash (get from https://my.telegram.org/apps)
- Bot Token (get from @BotFather)

## Installation

1. Clone the repository or download the files
2. Install the required packages:

```bash
pip install -r requirements.txt
```

3. Set up your credentials in `.env` file:

Create a `.env` file in the root directory with your credentials. You can use `.env.example` as a template:
```
API_ID=your_api_id
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
```

**Note**: If you encounter a "SESSION_REVOKED" error, delete the `.session` file in the project directory and restart the bot.

## Usage

Run the bot:

```bash
python main.py
```

## Commands

- `/start` - Start the bot and get a welcome message
- `/help` - Show available commands and usage instructions
- `/pdf [filename]` - Reply to an image with this command to convert it to PDF. If no filename is provided, it will use a unique filename based on user ID and timestamp.
- `/compress [filename]` - Reply to a PDF with this command to compress it. If no filename is provided, it will use a unique filename based on user ID and timestamp.

## How it Works

📷 *Image to PDF:*
1. User sends an image to the bot **(Automatic conversion!)**
2. OR user replies to an image with `/pdf` command (with optional filename)
3. Bot downloads the image
4. Bot converts the image to a PDF with automatic compression
5. Bot sends the PDF back to the user
6. Bot deletes temporary files

📄 *PDF Compression:*
1. User sends a PDF to the bot
2. User replies to the PDF with `/compress` command (with optional filename)
3. Bot downloads the PDF
4. Bot compresses the PDF using advanced optimization techniques
5. Bot sends the compressed PDF back to the user with size reduction information
6. Bot deletes temporary files

## Dependencies

- [Pyrogram](https://docs.pyrogram.org/) - Telegram MTProto API Framework
- [Pillow](https://pillow.readthedocs.io/en/stable/) - Python Imaging Library
- [PyMuPDF](https://pymupdf.readthedocs.io/en/latest/) - PDF manipulation library
- [python-dotenv](https://pypi.org/project/python-dotenv/) - Environment variable management

## Security

The bot uses environment variables to store sensitive credentials, which are automatically ignored by git through the `.gitignore` file.

## License

This project is open source and available under the MIT License.