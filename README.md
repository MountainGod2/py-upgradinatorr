# Upgradinatorr

Automated media upgrade search for Starr applications (Radarr, Sonarr, Lidarr, Readarr).

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
upgradinatorr -a radarr,sonarr

# Use custom config file
upgradinatorr -a radarr -c /path/to/config.conf

# Enable verbose output
upgradinatorr -a radarr --verbose

# Preview processing
upgradinatorr -a radarr --dry-run
```

### Docker Usage

Run with docker:

```bash
docker run --rm \
  -e PUID=99 \
  -e PGID=100 \
  -v /path/to/config:/config \
  mountaingod2/upgradinatorr:develop \
  -a radarr,sonarr --verbose
```

Or use docker-compose:

```yaml
version: '3.8'

services:
  upgradinatorr:
    image: mountaingod2/upgradinatorr:develop
    container_name: upgradinatorr
    environment:
      - PUID=99  # Set to your user ID (run `id -u`)
      - PGID=100  # Set to your group ID (run `id -g`)
    volumes:
      - /path/to/config:/config
    command: ["-a", "radarr,sonarr", "--verbose"]
```

**Environment Variables:**
- `PUID` - User ID to run as (default: 999)
- `PGID` - Group ID to run as (default: 999)

**Volumes:**
- `/config` - Directory containing your `upgradinatorr.conf` file

The container will automatically create a default config file from the example if one doesn't exist.

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