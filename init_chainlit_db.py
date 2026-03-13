"""
Initialize Chainlit database tables
Run this script once to create all necessary Chainlit tables in your PostgreSQL database
"""
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

async def init_chainlit_tables():
    """Create all Chainlit database tables"""
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    
    try:
        # Check PostgreSQL version and JSONB support
        pg_version = await conn.fetchval("SELECT version()")
        print(f"📊 PostgreSQL version: {pg_version[:50]}...")
        
        # Determine JSON type support
        # PostgreSQL 9.2 supports JSON, 9.4+ supports JSONB
        json_type = "JSONB"
        try:
            # Test if JSONB exists (PostgreSQL 9.4+)
            await conn.fetchval("SELECT '{}'::jsonb")
            print("✅ JSONB is supported")
        except Exception:
            # Fall back to JSON (PostgreSQL 9.2+)
            try:
                await conn.fetchval("SELECT '{}'::json")
                json_type = "JSON"
                print("⚠️ JSONB not available, using JSON instead")
            except Exception:
                # Last resort: use TEXT for very old PostgreSQL
                json_type = "TEXT"
                print("⚠️ JSON not available, using TEXT instead (data will be stored as text)")
        
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
        print("✅ Created Thread table")
        
        # Create Step table
        # Note: "end" is a reserved keyword, so we quote it
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
        print("✅ Created Step table")
        
        # Create User table
        await conn.execute(f"""
            CREATE TABLE IF NOT EXISTS "User" (
                id TEXT PRIMARY KEY,
                identifier TEXT UNIQUE,
                metadata {json_type},
                createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Created User table")
        
        # Create UserEnv table (for user environment variables)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS "UserEnv" (
                id TEXT PRIMARY KEY,
                user_id TEXT REFERENCES "User"(id) ON DELETE CASCADE,
                key TEXT,
                value TEXT,
                createdAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ Created UserEnv table")
        
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
        print("✅ Created Attachment table")
        
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
        print("✅ Created Feedback table")
        
        # Create indexes for better performance
        # PostgreSQL 9.2 doesn't support IF NOT EXISTS for indexes, so we check first
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
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_class 
                    WHERE relname = $1
                )
            """, idx_name)
            if not exists:
                await conn.execute(f'CREATE INDEX {idx_name} ON {table_name}({column_name})')
        
        print("✅ Created indexes")
        
        print("\n🎉 Chainlit database tables initialized successfully!")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_chainlit_tables())

