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

3. Set up your credentials in `config.py`:

```python
API_ID = "your_api_id"
API_HASH = "your_api_hash"
BOT_TOKEN = "your_bot_token"
```

## Usage

Run the bot:

```bash
python main.py
```

## Commands

- `/start` - Start the bot and get a welcome message
- `/pdf [filename]` - Reply to an image with this command to convert it to PDF. If no filename is provided, it will use "Pdfio.pdf" as default.

## How it Works

1. User sends an image to the bot
2. User replies to the image with `/pdf` command (with optional filename)
3. Bot downloads the image
4. Bot converts the image to a PDF with the specified filename
5. Bot sends the PDF back to the user
6. Bot deletes temporary files

## Dependencies

- [Pyrogram](https://docs.pyrogram.org/) - Telegram MTProto API Framework
- [Pillow](https://pillow.readthedocs.io/en/stable/) - Python Imaging Library

## License

This project is open source and available under the MIT License.