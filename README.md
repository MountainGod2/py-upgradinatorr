# Upgradinatorr

Automated media upgrade search for Starr applications (Radarr, Sonarr, Lidarr, Readarr).

## Installation

```bash
uv tool install upgradinatorr
```

Or install from source:

```bash
git clone https://github.com/yourusername/upgradinatorr
cd upgradinatorr
uv sync
source .venv/bin/activate  # or prefix the commands below with `uv run`
```

## Usage

```bash
# Process single application
upgradinatorr -a radarr

# Process multiple applications
upgradinatorr -a radarr,sonarr

# Process multiple instances
upgradinatorr -a radarr,radarr4k

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
  -v /mnt/user/appdata/upgradinatorr/config:/config \
  mountaingod2/upgradinatorr:latest \
  -a radarr,sonarr --verbose
```

Or use docker-compose:

```yaml
name: upgradinatorr

services:
  upgradinatorr:
    image: mountaingod2/upgradinatorr:latest
    container_name: upgradinatorr
    volumes:
      - /path/to/config:/config
    environment:
      - PUID=99
      - PGID=100
    command: ["-a", "radarr,sonarr", "--verbose"]
```

**Environment Variables:**
- `PUID` - User ID to run as (default: 999)
- `PGID` - Group ID to run as (default: 999)

**Volumes:**
- `/config` - Directory containing your `upgradinatorr.conf` file

The container will automatically create a default config file from the example if one doesn't exist.

## Configuration

App arguments passed to `-a/--apps` should match your config section names (case-insensitive).
For example, if your config has `[Radarr]` and `[Radarr4K]`, use `-a radarr,radarr4k`.

Create a `upgradinatorr.conf` file (see example from [original repo](https://github.com/angrycuban13/Just-A-Bunch-Of-Starr-Scripts/blob/main/Upgradinatorr/upgradinatorr-example.conf)):

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

- Python 3.12+
- aiohttp
- tenacity
- rich
- rich-click
- pydantic

## License

MIT

## Credits

Original PowerShell version by [angrycuban13](https://github.com/angrycuban13/Just-A-Bunch-Of-Starr-Scripts/blob/main/Upgradinatorr/)