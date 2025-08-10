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
# Get current mood (formatted display)
mood-get
# Get current mood (raw JSON)
mood-get --json
# Get current mood with custom server URL (for local development)
mood-get --url http://localhost:8080

# Update mood
mood-set happy
# Update mood with custom server URL (for local development)
mood-set content --url http://localhost:8080

# Stream mood updates
mood-stream
# In a different terminal
mood-set productive
```

### Updating the mood from the model

```javascript
const response = await fetch("https://emotibot-relay.fly.dev/mood", {
  method: "PUT",
  body: JSON.stringify({ mood: "happy" }),
});

const data = await response.json();
console.log(data);
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
