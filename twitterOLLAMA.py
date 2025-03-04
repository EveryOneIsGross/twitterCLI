from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import twitterCLI
from ollama import chat
import asyncio
import json

# Custom JSON encoder to handle datetime
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Data Models
class TwitterRequest(BaseModel):
    operation: str  # user, tweets, search, post, like, unlike, timeline, delete
    params: Dict[str, Any]

class TwitterResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def model_dump(self, *args, **kwargs):
        """Override model_dump to handle datetime serialization"""
        dump = super().model_dump(*args, **kwargs)
        dump['timestamp'] = dump['timestamp'].isoformat()
        return dump

class ConversationContext(BaseModel):
    """Maintains the conversation history and context"""
    messages: List[Dict[str, Any]] = []
    last_response: Optional[Dict[str, Any]] = None
    
    def add_user_message(self, message: str):
        self.messages.append({
            'role': 'user',
            'content': message,
            'timestamp': datetime.now().isoformat()
        })
    
    def add_assistant_message(self, message: str, api_response: Optional[Dict[str, Any]] = None):
        self.messages.append({
            'role': 'assistant',
            'content': message,
            'api_response': api_response,
            'timestamp': datetime.now().isoformat()
        })
        self.last_response = api_response

class StructuredTwitterAPI:
    """Structured interface to TwitterCLI functionality"""
    
    def __init__(self):
        self.api = twitterCLI.TwitterAPI()
        self.user_id_cache: Dict[str, str] = {}

    def execute(self, request: TwitterRequest) -> TwitterResponse:
        """Execute Twitter API operation with structured input/output"""
        
        operation_map = {
            'user': lambda p: self.api.get_user_info(p['username']),
            'tweets': self._handle_tweets,
            'search': lambda p: self.api.search_tweets(p['query'], p.get('limit', 10)),
            'post': lambda p: self.api.create_tweet(
                text=p['text'],
                media_path=p.get('media_path'),
                reply_to_id=p.get('reply_to_id')
            ),
            'like': lambda p: self.api.like_tweet(p['tweet_id']),
            'unlike': lambda p: self.api.unlike_tweet(p['tweet_id']),
            'timeline': lambda p: self.api.get_home_timeline(p.get('limit', 20)),
            'delete': lambda p: self.api.delete_tweet(p['tweet_id'])
        }

        try:
            if request.operation not in operation_map:
                return TwitterResponse(
                    success=False,
                    error=f"Unsupported operation: {request.operation}"
                )

            result = operation_map[request.operation](request.params)
            
            # Cache user ID if this was a user info request
            if request.operation == 'user' and 'error' not in result and 'data' in result:
                username = request.params.get('username')
                if username and 'id' in result['data']:
                    self.user_id_cache[username.lower()] = result['data']['id']
            
            return TwitterResponse(
                success='error' not in result,
                data=result if 'error' not in result else None,
                error=result.get('error')
            )

        except Exception as e:
            return TwitterResponse(success=False, error=str(e))

    def _handle_tweets(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle the two-step tweets operation with caching"""
        username = params['username'].lower()
        
        # Try to get user ID from cache first
        user_id = self.user_id_cache.get(username)
        
        if not user_id:
            # If not in cache, fetch user info
            user_result = self.api.get_user_info(username)
            if 'error' in user_result:
                return user_result
            user_id = user_result['data']['id']
            self.user_id_cache[username] = user_id
        
        return self.api.get_user_tweets(
            user_id,
            params.get('limit', 10)
        )

async def process_nlp_request(query: str, context: ConversationContext, model: str = 'hermes3', max_retries: int = 3) -> TwitterRequest:
    """Convert natural language query to structured request using Ollama with context"""
    
    # Create system context with examples and conversation history
    system_context = {
        'role': 'system',
        'content': """You are a Twitter API request converter. Convert natural language queries into structured API requests.
Available operations and their parameters:
- user: {'username': str}
- tweets: {'username': str, 'limit': int}
- search: {'query': str, 'limit': int}
- post: {'text': str, 'media_path': Optional[str], 'reply_to_id': Optional[str]}
- like: {'tweet_id': str}
- unlike: {'tweet_id': str}
- timeline: {'limit': int}
- delete: {'tweet_id': str}

Consider the conversation history and last API response when converting new queries.
If a query references previous results, use that context to form the request."""
    }
    
    # Add conversation history to help with context
    messages = [system_context] + context.messages
    
    # Add current query
    messages.append({
        'role': 'user',
        'content': f"Convert this query to a Twitter API request (considering previous context if relevant): {query}"
    })
    
    for attempt in range(max_retries):
        try:
            response = chat(
                messages=messages,
                model=model,
                format='json'
            )
            
            if not response or not hasattr(response, 'message') or not response.message.content:
                raise ValueError("Invalid response format from Ollama")
                
            try:
                request_data = json.loads(response.message.content)
                return TwitterRequest(**request_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON response: {str(e)}")
                
        except Exception as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to process NLP request after {max_retries} attempts: {str(e)}")
            await asyncio.sleep(1)  # Wait before retry

async def interactive_session():
    """Run an interactive Twitter API session"""
    api = StructuredTwitterAPI()
    context = ConversationContext()
    
    print("\n=== Twitter API Interactive Session ===")
    print("Available commands:")
    print("- user <username>: Get user information")
    print("- tweets <username> [limit]: Get user's tweets")
    print("- search <query> [limit]: Search for tweets")
    print("- timeline [limit]: Get your home timeline")
    print("- like <tweet_id>: Like a tweet")
    print("- unlike <tweet_id>: Unlike a tweet")
    print("- post <text>: Post a new tweet")
    print("Type 'exit' to quit.")
    
    while True:
        try:
            query = input("\nYou: ").strip()
            if query.lower() in ['exit', 'quit', 'bye']:
                print("\nGoodbye! 👋")
                break
                
            # Add user query to context
            context.add_user_message(query)
            
            # Process query with context
            print("\n🤔 Processing query...")
            request = await process_nlp_request(query, context)
            
            # Show generated request
            print("\n📝 Generated API Request:")
            print(json.dumps(request.model_dump(), indent=2, cls=DateTimeEncoder))
            
            # Execute request
            print("\n🚀 Executing request...")
            response = api.execute(request)  # Now passing the TwitterRequest directly
            
            # Add response to context
            if response.success:
                result_summary = f"✅ Successfully executed {request.operation} operation."
                context.add_assistant_message(result_summary, response.data)
            else:
                error_msg = f"❌ Error executing {request.operation}: {response.error}"
                context.add_assistant_message(error_msg, None)
            
            # Display response
            print("\n📊 API Response:")
            print(json.dumps(response.model_dump(), indent=2, cls=DateTimeEncoder))
            
            # Show cache status
            if hasattr(api, 'user_id_cache'):
                cached_users = len(api.user_id_cache)
                if cached_users > 0:
                    print(f"\n💾 User ID cache: {cached_users} users cached")
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            context.add_assistant_message(f"Error: {str(e)}", None)

if __name__ == "__main__":
    asyncio.run(interactive_session())