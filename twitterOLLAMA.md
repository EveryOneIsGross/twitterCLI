# Twitter CLI with Natural Language Processing

## Prerequisites

- Python 3.10+
- Ollama installed and running locally
- Twitter API credentials (OAuth 1.0a)
- Hermes3 model installed in Ollama (`ollama pull hermes3`)

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your Twitter API credentials in `.env`:
```env
TWITTER_API_KEY=your_consumer_key
TWITTER_API_SECRET=your_consumer_secret
```

## Usage

Start the interactive session:
```bash
python twitterOLLAMA.py
```

### Available Commands

You can use natural language to interact with Twitter. Examples:

- "Show me @username's profile"
- "Get the last 5 tweets from @username"
- "Search for tweets about AI and blockchain"
- "Post a new tweet saying Hello World!"
- "Like tweet with ID 123456789"
- "Show my home timeline"
- "Unlike the last tweet I liked"

### Example Interaction

```
You: show me elon musk's latest tweets

🤔 Processing query...

📝 Generated API Request:
{
  "operation": "tweets",
  "params": {
    "username": "elonmusk",
    "limit": 10
  }
}

🚀 Executing request...

📊 API Response:
{
  "success": true,
  "data": {
    // Tweet data here
  },
  "timestamp": "2024-01-19T10:30:00"
}
```

## Features in Detail

### Conversation Context
- Maintains history of interactions
- References previous queries and responses
- Enables context-aware commands

### Structured Data Models
- `TwitterRequest`: Validates and structures API requests
- `TwitterResponse`: Standardizes API responses
- `ConversationContext`: Manages conversation state

### Caching
- Caches user IDs to reduce API calls
- Displays cache statistics during session

### Error Handling
- Retries on failed LLM requests
- Graceful error reporting
- Rate limit awareness

## Technical Details

### Components
- `StructuredTwitterAPI`: Interface to Twitter API operations
- `process_nlp_request`: Converts natural language to structured requests
- `interactive_session`: Manages the CLI interaction loop

### Data Flow
1. User inputs natural language query
2. Ollama processes query with context
3. Query converted to structured request
4. Request executed against Twitter API
5. Response formatted and displayed
6. Context updated for future queries

## Error Codes

The API returns structured errors in the following format:
```json
{
  "success": false,
  "error": "Error message here",
  "timestamp": "2024-01-19T10:30:00"
}
``` 