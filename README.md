# Emotibot Relay

Relay webservice for emotibot art project (BM25 Honorarium).

This is a simple web-server that can receive mood updates from the model and act as a relay for the on-Playa robot controller.

## Quick Start

### Prerequisites

- [mise](https://mise.jdx.dev/) for runtime management

### Installation

```bash
git clone https://github.com/biasedbit/emotibot-relay.git
cd emotibot-relay
mise install
uv sync --dev
```

### Running the Server

```bash
# Via docker compose
docker compose up -d
# Directly using UV with hot-reload
uv run emotibot-server --reload
```

The server will be available at `http://localhost:8000`.

### API Endpoints

#### Health Check

```bash
GET /
```

Returns service status.

#### Get Current Mood

```bash
GET /mood
```

Returns the current mood state.

#### Update Mood

```bash
PUT /mood
Content-Type: application/json

{
  "mood": "happy"
}
```

Updates the current mood and notifies all connected SSE clients.

#### Stream Mood Updates

```bash
GET /mood/stream
Accept: text/event-stream
```

Establishes an SSE connection to receive real-time mood updates.

### CLI Tools

The project includes CLI tools to test and interact with the service:

```bash
# Get current mood from localhost (formatted display)
mood-get
# Get current mood from localhost (raw JSON)
mood-get --json
# Get current mood from production server
mood-get --url https://emotibot-relay.fly.dev
# Using curl
curl http://localhost:8000/mood

# Update mood from localhost
mood-set happy
# Update mood in the production server
mood-set happy --url https://emotibot-relay.fly.dev
# Using curl
curl -X PUT --json '{"mood":"happy"}' https://emotibot-relay.fly.dev/mood

# Stream mood updates from localhost
mood-stream
# Stream mood updates from production server
mood-stream --url https://emotibot-relay.fly.dev
# Using curl
curl -N https://emotibot-relay.fly.dev/mood/stream
```

### Updating the mood from the model

```javascript
await fetch("https://emotibot-relay.fly.dev/mood", {
  method: "PUT",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ mood: "happy" }),
});
```

## Development

### Running Tests

```bash
# Run tests
uv run pytest

# Type Checking
uv run mypy emotibot_relay/

# Linting & formatting
uv run ruff check .
uv run ruff format .
```

## Deployment

The application is designed for easy deployment using Docker and Docker Compose.
The in-memory storage is suitable for single-instance deployments.
For multi-instance deployments, existing `MoodStore` should be replaced with e.g. a Redis-backed implementation.

To deploy to fly.io after making changes, run:

```bash
fly deploy
```

Server runs at `https://emotibot-relay.fly.dev`.

## License

MIT
