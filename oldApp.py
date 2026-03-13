import os
from dotenv import load_dotenv
import asyncio
import asyncpg  # Import asyncpg before using it

load_dotenv()

# CRITICAL: Initialize Chainlit tables BEFORE importing chainlit
# This must happen synchronously at module load time
async def _create_chainlit_tables():
    """Create Chainlit tables before Chainlit tries to use them"""
    try:
        conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
        try:
            # Check if Thread table exists
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'Thread'
                )
            """)
            
            if not exists:
                print("🔧 Creating Chainlit database tables...")
                
                # Check if JSONB is supported, fall back to JSON if not
                json_type = "JSONB"
                try:
                    await conn.fetchval("SELECT '{}'::jsonb")
                    print("✅ JSONB is supported")
                except Exception:
                    try:
                        await conn.fetchval("SELECT '{}'::json")
                        json_type = "JSON"
                        print("⚠️ Using JSON instead of JSONB")
                    except Exception:
                        json_type = "TEXT"
                        print("⚠️ Using TEXT instead of JSON (very old PostgreSQL)")
                
                await conn.execute(f'CREATE TABLE "Thread" (id TEXT PRIMARY KEY, name TEXT, user_id TEXT, user_identifier TEXT, tags TEXT[], metadata {json_type}, steps {json_type}, createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updatedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
                await conn.execute(f'CREATE TABLE "Step" (id TEXT PRIMARY KEY, name TEXT, type TEXT, thread_id TEXT REFERENCES "Thread"(id) ON DELETE CASCADE, parent_id TEXT, disable_feedback BOOLEAN DEFAULT FALSE, streaming BOOLEAN DEFAULT FALSE, wait_for_answer BOOLEAN DEFAULT FALSE, is_error BOOLEAN DEFAULT FALSE, metadata {json_type}, tags TEXT[], input TEXT, output TEXT, createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP, start TIMESTAMP, "end" TIMESTAMP, generation {json_type}, show_input BOOLEAN DEFAULT TRUE, language TEXT)')
                await conn.execute(f'CREATE TABLE "User" (id TEXT PRIMARY KEY, identifier TEXT UNIQUE, metadata {json_type}, createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
                await conn.execute('CREATE TABLE "UserEnv" (id TEXT PRIMARY KEY, user_id TEXT REFERENCES "User"(id) ON DELETE CASCADE, key TEXT, value TEXT, createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
                await conn.execute('CREATE TABLE "Attachment" (id TEXT PRIMARY KEY, thread_id TEXT REFERENCES "Thread"(id) ON DELETE CASCADE, step_id TEXT REFERENCES "Step"(id) ON DELETE CASCADE, name TEXT, path TEXT, size INTEGER, type TEXT, createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
                await conn.execute('CREATE TABLE "Feedback" (id TEXT PRIMARY KEY, step_id TEXT REFERENCES "Step"(id) ON DELETE CASCADE, value INTEGER, comment TEXT, "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
                
                # Create indexes (PostgreSQL 9.2 doesn't support IF NOT EXISTS for indexes)
                indexes = [
                    ('idx_step_thread_id', '"Step"', 'thread_id'),
                    ('idx_step_parent_id', '"Step"', 'parent_id'),
                    ('idx_thread_user_id', '"Thread"', 'user_id'),
                    ('idx_userenv_user_id', '"UserEnv"', 'user_id'),
                    ('idx_attachment_thread_id', '"Attachment"', 'thread_id'),
                    ('idx_attachment_step_id', '"Attachment"', 'step_id'),
                    ('idx_feedback_step_id', '"Feedback"', 'step_id'),
                ]
                for idx_name, table_name, column_name in indexes:
                    # Check if index exists using pg_class (works in PostgreSQL 9.2+)
                    exists = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM pg_class WHERE relname = $1)", idx_name)
                    if not exists:
                        await conn.execute(f'CREATE INDEX {idx_name} ON {table_name}({column_name})')
                
                print("✅ Chainlit tables created successfully!")
        finally:
            await conn.close()
    except Exception as e:
        print(f"⚠️ Warning: Could not create Chainlit tables: {e}")

# Run table creation synchronously before Chainlit imports
try:
    # Try to get existing loop, or create new one
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Can't run in already-running loop, will create in on_chat_start
            print("⚠️ Event loop already running, tables will be created on chat start")
        else:
            loop.run_until_complete(_create_chainlit_tables())
    except RuntimeError:
        # No event loop exists, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_create_chainlit_tables())
        loop.close()
except Exception as e:
    print(f"⚠️ Could not initialize tables at module load: {e}")
    print("💡 Tables will be created when chat starts")

# NOW import chainlit (after tables are created)
import chainlit as cl
from groq import AsyncGroq
from datetime import datetime
# asyncpg already imported at top

client = AsyncGroq()

# Database connection pool
db_pool = None

async def init_chainlit_tables():
    """Initialize Chainlit database tables if they don't exist"""
    async with db_pool.acquire() as conn:
        try:
            # Check if Thread table exists
            table_check = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'Thread'
                )
            """)
            
            if not table_check:
                print("🔧 Initializing Chainlit database tables...")
                
                # Check if JSONB is supported, fall back to JSON if not
                json_type = "JSONB"
                try:
                    await conn.fetchval("SELECT '{}'::jsonb")
                    print("✅ JSONB is supported")
                except Exception:
                    try:
                        await conn.fetchval("SELECT '{}'::json")
                        json_type = "JSON"
                        print("⚠️ Using JSON instead of JSONB")
                    except Exception:
                        json_type = "TEXT"
                        print("⚠️ Using TEXT instead of JSON (very old PostgreSQL)")
                
                # Create Thread table
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS "Thread" (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        user_id TEXT,
                        user_identifier TEXT,
                        tags TEXT[],
                        metadata {json_type},
                        steps {json_type},
                        createdat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updatedat TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create Step table
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS "Step" (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        type TEXT,
                        thread_id TEXT REFERENCES "Thread"(id) ON DELETE CASCADE,
                        parent_id TEXT,
                        disable_feedback BOOLEAN DEFAULT FALSE,
                        streaming BOOLEAN DEFAULT FALSE,
                        wait_for_answer BOOLEAN DEFAULT FALSE,
                        is_error BOOLEAN DEFAULT FALSE,
                        metadata {json_type},
                        tags TEXT[],
                        input TEXT,
                        output TEXT,
                        createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        start TIMESTAMP,
                        "end" TIMESTAMP,
                        generation {json_type},
                        show_input BOOLEAN DEFAULT TRUE,
                        language TEXT
                    )
                """)
                
                # Create User table
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS "User" (
                        id TEXT PRIMARY KEY,
                        identifier TEXT UNIQUE,
                        metadata {json_type},
                        createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create UserEnv table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS "UserEnv" (
                        id TEXT PRIMARY KEY,
                        user_id TEXT REFERENCES "User"(id) ON DELETE CASCADE,
                        key TEXT,
                        value TEXT,
                        createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create Attachment table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS "Attachment" (
                        id TEXT PRIMARY KEY,
                        thread_id TEXT REFERENCES "Thread"(id) ON DELETE CASCADE,
                        step_id TEXT REFERENCES "Step"(id) ON DELETE CASCADE,
                        name TEXT,
                        path TEXT,
                        size INTEGER,
                        type TEXT,
                        createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create Feedback table (required by Chainlit)
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS "Feedback" (
                        id TEXT PRIMARY KEY,
                        step_id TEXT REFERENCES "Step"(id) ON DELETE CASCADE,
                        value INTEGER,
                        comment TEXT,
                        "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes (PostgreSQL 9.2 doesn't support IF NOT EXISTS for indexes)
                indexes = [
                    ('idx_step_thread_id', '"Step"', 'thread_id'),
                    ('idx_step_parent_id', '"Step"', 'parent_id'),
                    ('idx_thread_user_id', '"Thread"', 'user_id'),
                    ('idx_userenv_user_id', '"UserEnv"', 'user_id'),
                    ('idx_attachment_thread_id', '"Attachment"', 'thread_id'),
                    ('idx_attachment_step_id', '"Attachment"', 'step_id'),
                    ('idx_feedback_step_id', '"Feedback"', 'step_id'),
                ]
                for idx_name, table_name, column_name in indexes:
                    # Check if index exists using pg_class (works in PostgreSQL 9.2+)
                    exists = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM pg_class WHERE relname = $1)", idx_name)
                    if not exists:
                        await conn.execute(f'CREATE INDEX {idx_name} ON {table_name}({column_name})')
                
                print("✅ Chainlit database tables initialized!")
            else:
                print("✅ Chainlit database tables already exist")
                
        except Exception as e:
            print(f"⚠️ Warning: Could not initialize Chainlit tables: {e}")
            print("💡 You can run 'python init_chainlit_db.py' manually to create tables")

@cl.on_chat_start
async def start():
    """Initialize database connection pool when chat starts"""
    global db_pool
    if db_pool is None:
        try:
            db_pool = await asyncpg.create_pool(
                os.getenv("NEOX_DATABASE_URL"),
                min_size=1,
                max_size=10
            )
            print("✅ Connected to database!")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            raise
    
    # Initialize Chainlit tables
    await init_chainlit_tables()
    
    # Example: Read some data from database on startup
    async with db_pool.acquire() as conn:
        # Check what tables exist
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        print(f"📊 Available tables: {[t['table_name'] for t in tables]}")

@cl.on_message
async def on_message(message: cl.Message):
    try:
        print(f"📨 Received message: {message.content[:50]}...")
        session_id = cl.user_session.get("id")
        
        # Initialize conversation history if it doesn't exist
        conversation_history = cl.user_session.get("conversation_history")
        if conversation_history is None:
            conversation_history = []
            cl.user_session.set("conversation_history", conversation_history)
        
        # Check if database pool is available
        if db_pool is None:
            reply = "❌ Database connection not available. Please restart the chat."
            await cl.Message(content=reply).send()
            return
        
        print("🔍 Fetching database schema...")
        # Get database schema information with timeout
        try:
            async with db_pool.acquire() as conn:
                # Get all tables
                tables = await conn.fetch("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                table_list = [t['table_name'] for t in tables[:20]]
                print(f"📊 Found {len(table_list)} tables")
                
                # Get detailed schema with columns (limit to prevent slowdown)
                schema_info = ""
                for table in table_list:  # Limit to first 20 tables
                    columns = await conn.fetch(f"""
                        SELECT column_name, data_type 
                        FROM information_schema.columns 
                        WHERE table_name = '{table}'
                        ORDER BY ordinal_position
                    """)
                    col_details = ', '.join([f"{c['column_name']} ({c['data_type']})" for c in columns[:10]])  # Limit columns
                    schema_info += f"\n  • {table}: {col_details}"
        except Exception as e:
            print(f"❌ Schema fetch error: {e}")
            reply = f"❌ Could not fetch database schema: {str(e)}"
            await cl.Message(content=reply).send()
            return
        
        print("🤖 Calling AI to generate response...")
        # First, ask AI if this is a database query request and to generate SQL
        try:
            # Build messages array with conversation history
            messages_array = [
                {
                    "role": "system",
                    "content": f"""You are a PostgreSQL database assistant. You can execute READ-ONLY queries.

DATABASE SCHEMA:
{schema_info}

backup
- You will have all the tables described to you. You will pick one table to query from.
- If the user asks ANY question about data in the database, you MUST respond with ONLY a SQL SELECT query
- Start your response with "SQL:" followed by the query
- NEVER guess or make up data - ALWAYS generate SQL to query the actual database
- Use proper PostgreSQL syntax
- ONLY use SELECT statements (no INSERT, UPDATE, DELETE, CREATE, DROP, etc.)

CRITICAL INSTRUCTIONS:
- If the user asks ANY question about data in the database, you MUST respond with ONLY a SQL SELECT query
- Start your response with "SQL:" followed by the query
- NEVER guess or make up data - ALWAYS generate SQL to query the actual database
- Use proper PostgreSQL syntax
- ONLY use SELECT statements (no INSERT, UPDATE, DELETE, CREATE, DROP, etc.)
- If the user is asking a conversational question (not about querying data), respond normally without "SQL:"

PREFIX DICTIONARY:
Each of these prefixes in the database refer to the following-

blca: Bladder Urothelial Carcinoma
brca: Breast Invasive Carcinoma
cesc: Cervical Squamous Cell Carcinoma and Endocervical Adenocarcinoma
coad: Colon Adenocarcinoma
esca: Esophageal Carcinoma
gbm: Glioblastoma Multiforme
hnsc: Head and Neck Squamous Cell Carcinoma
kich: Kidney Chromophobe
kirc: Kidney Renal Clear Cell Carcinoma
lgg: Brain Lower Grade Glioma
lihc: Liver Hepatocellular Carcinoma
luad: Lung Adenocarcinoma
lusc: Lung Squamous Cell Carcinoma
ov: Ovarian Serous Cystadenocarcinoma
paad: Pancreatic Adenocarcinoma
pcpg: Pheochromocytoma and Paraganglioma
prad: Prostate Adenocarcinoma
read: Rectum Adenocarcinoma
sarc: Sarcoma
skcm: Skin Cutaneous Melanoma
stad: Stomach Adenocarcinoma
tgct: Testicular Germ Cell Tumors
thca: Thyroid Carcinoma
ucec: Uterine Corpus Endometrial Carcinoma

INFORMATION ON TERMS:
Subtypes refers to signatures in the database. Use distinct call to get the number of signatures from full_sig tables. _signature shows what sample are a part of what signature.

UIDs are usually used for splicing events.

EXAMPLES:
User: "How many cancers are in the database?"
You: SQL: SELECT COUNT(DISTINCT cancer) as cancer_count FROM survival;

User: "What cancers are in the database?"
You: SQL: SELECT DISTINCT cancer FROM survival ORDER BY cancer;

User: How many splicing junctions exist in the database?
You: SQL: SELECT COUNT(DISTINCT uid)

User: "Show me all users"
You: SQL: SELECT * FROM users LIMIT 10;

User: "What's the weather like?"
You: I don't have access to weather information, but I can help you query the database!

"""
                },
            ]
            
            # Add conversation history (last 10 exchanges to avoid token limits)
            for hist_msg in conversation_history[-10:]:
                messages_array.append(hist_msg)
            
            # Add current user message
            messages_array.append({
                "role": "user",
                "content": message.content
            })
            
            print(f"📝 Including {len(conversation_history)} previous messages in context")
            
            # Retry logic with exponential backoff
            max_retries = 3
            retry_delay = 2  # Start with 2 seconds
            
            response = None
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    print(f"🔄 Attempting AI call (attempt {attempt + 1}/{max_retries})...")
                    response = await client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=messages_array,
                        temperature=0.2,
                        timeout=60.0,  # 60 second timeout
                    )
                    print(f"✅ AI call succeeded on attempt {attempt + 1}")
                    break  # Success, exit retry loop
                except Exception as retry_error:
                    last_error = retry_error
                    if attempt < max_retries - 1:  # Don't wait on last attempt
                        print(f"⚠️ Attempt {attempt + 1} failed, waiting {retry_delay}s before retry...")
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff: 2s, 4s, 8s
                    else:
                        print(f"❌ All {max_retries} attempts failed")
            
            if response is None:
                raise last_error  # Re-raise the last error to be caught by outer except
            
            ai_response = response.choices[0].message.content.strip()
            print(f"🤖 AI response: {ai_response[:100]}...")
            
            # Update conversation history with this exchange
            conversation_history.append({
                "role": "user",
                "content": message.content
            })
            conversation_history.append({
                "role": "assistant",
                "content": ai_response
            })
            
            # Keep only last 20 messages (10 exchanges) to avoid token limits
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]
                cl.user_session.set("conversation_history", conversation_history)
        except Exception as e:
            # Get detailed error information
            error_type = type(e).__name__
            error_message = str(e)
            
            # Build detailed error information
            error_details = [f"Type: {error_type}", f"Message: {error_message}"]
            
            # Extract all available attributes from the exception
            if hasattr(e, '__dict__'):
                for attr_name, attr_value in e.__dict__.items():
                    if attr_name not in ['__cause__', '__traceback__', '__suppress_context__']:
                        try:
                            error_details.append(f"{attr_name}: {attr_value}")
                        except:
                            error_details.append(f"{attr_name}: <unable to stringify>")
            
            # Check for underlying cause (chained exceptions)
            if hasattr(e, '__cause__') and e.__cause__:
                cause = e.__cause__
                error_details.append(f"\nUnderlying Cause: {type(cause).__name__}: {str(cause)}")
                if hasattr(cause, '__dict__'):
                    for attr_name, attr_value in cause.__dict__.items():
                        try:
                            error_details.append(f"  Cause.{attr_name}: {attr_value}")
                        except:
                            pass
            
            # Check for common API error attributes
            for attr in ['status_code', 'response', 'body', 'request', 'code', 'message', 'error']:
                if hasattr(e, attr):
                    try:
                        value = getattr(e, attr)
                        error_details.append(f"{attr}: {value}")
                    except:
                        pass
            
            # Check if it's a connection error with more details
            if 'Connection' in error_type or 'connection' in error_message.lower():
                error_details.append("\n🔍 Connection Error Details:")
                error_details.append("  - Check your internet connection")
                error_details.append("  - Verify Groq API is accessible")
                error_details.append("  - Check firewall/proxy settings")
                if hasattr(e, 'request'):
                    try:
                        req = e.request
                        error_details.append(f"  - Request URL: {getattr(req, 'url', 'N/A')}")
                        error_details.append(f"  - Request method: {getattr(req, 'method', 'N/A')}")
                    except:
                        pass
            
            # Print full traceback for debugging
            import traceback
            full_traceback = traceback.format_exc()
            
            error_summary = "\n".join(error_details)
            print(f"❌ AI call error:\n{error_summary}")
            print(f"\nFull traceback:\n{full_traceback}")
            
            reply = f"❌ Error calling AI: {error_type}\n{error_message}"
            await cl.Message(content=reply).send()
            return
        
        # Check if AI returned a SQL query
        if ai_response.startswith("SQL:"):
            # Extract the SQL query
            sql_query = ai_response[4:].strip()
            print(f"🗄️ Executing SQL: {sql_query}")
            
            # Safety check: Only allow SELECT statements
            if not sql_query.upper().startswith('SELECT'):
                reply = "⚠️ Only SELECT queries are allowed for security reasons."
            else:
                # Execute the query with timeout
                async with db_pool.acquire() as conn:
                    try:
                        # Set statement timeout to 10 seconds
                        await conn.execute("SET statement_timeout = '40s'")
                        results = await conn.fetch(sql_query)
                        print(f"✅ Query returned {len(results)} rows")
                        
                        # Format results nicely based on user's question
                        user_msg_lower = message.content.lower()
                        
                        if results:
                            # Special handling for "how many cancers" question
                            if "how many" in user_msg_lower and "cancer" in user_msg_lower:
                                # Get the count from results
                                count = len(results) if not sql_query.upper().count("COUNT") else results[0].get('cancer_count') or results[0].get('count') or len(results)
                                reply = f"**Number of cancers:** {count}\n\n"
                                reply += "💡 You might want to ask: 'What cancers are in the database?' or 'How many splicing junctions exist in the database?'"
                            
                            # Special handling for "what cancers" question
                            elif ("what cancer" in user_msg_lower or "which cancer" in user_msg_lower or "list cancer" in user_msg_lower) and "are" in user_msg_lower:
                                # Get the actual cancer values from results
                                cancers = []
                                for row in results:
                                    row_dict = dict(row)
                                    # Get the cancer value (could be in 'cancer' column or first column)
                                    cancer_val = row_dict.get('cancer') or list(row_dict.values())[0]
                                    cancers.append(str(cancer_val))
                                
                                reply = f"**Cancers in the database:** ({len(cancers)} total)\n\n"
                                for i, cancer in enumerate(cancers, 1):
                                    reply += f"{i}. {cancer}\n"
                                reply += "\n💡 You might want to ask: 'How many splicing events for [cancer type]' or 'How many subtypes are available for [cancer type]?'"
                            
                            # Default format - show query and results
                            else:
                                # Show the query that was executed
                                reply = f"**Executed Query:**\n```sql\n{sql_query}\n```\n\n"
                                reply += f"**Results:** ({len(results)} rows)\n\n"
                                
                                # Display results as a formatted table
                                for i, row in enumerate(results, 1):
                                    reply += f"**Row {i}:**\n"
                                    for key, value in dict(row).items():
                                        reply += f"  • {key}: {value}\n"
                                    reply += "\n"
                                    
                                    # Limit display to avoid overwhelming output
                                    if i >= 20:
                                        reply += f"... and {len(results) - 20} more rows\n"
                                        break
                        else:
                            reply = f"**Executed Query:**\n```sql\n{sql_query}\n```\n\n✅ Query executed successfully but returned no results."
                            
                    except Exception as e:
                        print(f"❌ Query execution error: {e}")
                        reply = f"❌ **Error executing query:**\n```sql\n{sql_query}\n```\n\n**Error:** {str(e)}"
        else:
            # Normal conversational response
            print("💬 Normal conversation response")
            reply = ai_response
        
        print("📤 Sending reply...")
        
        # ✅ HERE: Capture the chatbot's response as a variable
        current_message = reply  # This is the chatbot's response as a string
        
        # Now you can do whatever you want with it:
        print(f"💬 Chatbot said: {current_message[:100]}...")  # Print first 100 chars
        
        # Store it in a list/database/file/etc
        # Example: save to a global list
        # conversation_history.append({"user": message.content, "bot": current_message})
        
        await cl.Message(content=reply).send()
        print("✅ Message sent successfully")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"❌ An unexpected error occurred: {str(e)}").send()