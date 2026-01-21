# Upgradinatorr

Automated media upgrade search for Starr applications (Radarr, Sonarr, Lidarr, Readarr).

## Features

- Automated upgrade searches across multiple Starr applications
- Flexible filtering by quality profiles, tags, and status
- Discord and Notifiarr webhook notifications
- Async operations for fast performance
- Beautiful CLI with Rich formatting
- Type-safe configuration with Pydantic

## Installation

```bash
pip install upgradinatorr
```

Or install from source:

```bash
git clone https://github.com/yourusername/upgradinatorr
cd upgradinatorr
pip install -e .
```

## Usage

```bash
# Process single application
upgradinatorr -a radarr

# Process multiple applications
upgradinatorr -a radarr -a sonarr

# Use custom config file
upgradinatorr -a radarr -c /path/to/config.conf

# Enable verbose output
upgradinatorr -a radarr --verbose
```

## Configuration

Create a `upgradinatorr.conf` file (see example in repository):

```ini
[Notifications]
DiscordWebhook=https://discord.com/api/webhooks/...
NotifiarrPassthroughWebhook=https://notifiarr.com/api/v1/notification/passthrough/...
NotifiarrPassthroughDiscordChannelId=123456789

[Radarr]
ApiKey=your_api_key_here
Count=10
Monitored=true
MovieStatus=released
TagName=upgrade
Unattended=false
Url=http://localhost:7878

[Sonarr]
ApiKey=your_api_key_here
Count=5
Monitored=true
SeriesStatus=continuing
TagName=upgrade
Unattended=false
Url=http://localhost:8989
```

## Requirements

- Python 3.10+
- aiohttp
- rich
- rich-click
- pydantic

## License

MIT

## Credits

Original PowerShell version by angrycuban13
Python port maintains the same functionality with async improvements