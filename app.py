import os
from dotenv import load_dotenv
import asyncio
import asyncpg  # Import asyncpg before using it

load_dotenv()

# Import chainlit
import chainlit as cl
from langchain_groq import ChatGroq
from tools.neoxCancerSpecific import query_neoxCancerSpecific
from tools.neoxUniversal import query_neoxUniversal
from tools.neoxQueryConstruction import query_neoxQueryConstruction
from datetime import datetime
# asyncpg already imported at top

client = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.3)
client_with_tools = client.bind_tools([query_neoxCancerSpecific, query_neoxUniversal, query_neoxQueryConstruction])

# Testing mode: disabled - full flow with query construction

# Database connection pool
db_pool = None

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
        '''try:
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
        '''

        print("🤖 Calling AI to generate response...")
        mode_prefix = ""
        # First, ask AI if this is a database query request and to generate SQL
        try:
            # Build messages array with conversation history
            messages_array = [
                {
                    "role": "system",
                    "content": f""""You are a PostgreSQL database assistant. You can execute READ-ONLY queries.

CRITICAL INSTRUCTIONS:
- Tell the user which tables to query from and the relevant columns (based on the prompt), and the USE value for each column.
- If the user is asking a conversational question (not about querying data), respond normally without "SQL:"

TOOL USAGE WORKFLOW:
1. First, call query_neoxCancerSpecific and query_neoxUniversal to get tables and columns information.
   
   **MULTIPLE CANCERS = MULTIPLE TOOL CALLS (REQUIRED)**
   If the user mentions MULTIPLE cancers in their question, you MUST call query_neoxCancerSpecific MULTIPLE times - once for EACH cancer. This is NOT optional.
   
   Examples:
   - User: "How many splicing events are present for LUAD and BRCA?"
     → You MUST call: query_neoxCancerSpecific(cancer_prefix="luad", table_suffix="_splice") AND query_neoxCancerSpecific(cancer_prefix="brca", table_suffix="_splice")
   - User: "Compare BRCA, COAD, and LUAD"
     → You MUST call the tool THREE times: once for "brca", once for "coad", once for "luad"
   
   DO NOT try to combine multiple cancers into one tool call. Each cancer requires its own separate tool call.
   
2. Decide the USE value for each column (RETURN or FILTER) and QUERYTYPE(s) for each table (COUNT, DISTINCT, FILTERED). Then call query_neoxQueryConstruction with table_info as a JSON string. Combine outputs from multiple tool calls into one tables array.

CANCER PREFIX DESCRIPTIONS:

IMPORTANT: When users mention cancer names (e.g., "LUAD", "BRCA", "Breast", "Lung Adenocarcinoma"), map them to these lowercase prefixes:
- LUAD, Lung Adenocarcinoma, Lung ADC → luad
- BRCA, Breast, Breast Cancer → brca
- COAD, Colon, Colon Cancer → coad
- etc.

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

OTHER DEFINITIONS:

Subtypes are equivalent to signatures.

Here are some examples of gene symbols: TP53, IRF8, AAR2, DPM1, SCYL3, KRIT1. If you see symbols like these, the user is referring to a gene.

Cancers with poor prognosis have very low 5 year survival rates.

TABLE TYPES:
There are two types of tables to query from.

TABLE TYPE 1: Cancer specific tables

TABLE TYPE 2: Universal tables

QUERYTYPE:

Special object for this program. Every selected table has a(n) associated QUERYTYPE(s).

FILTERED - this QUERYTYPE uses a WHERE condition in the SQL statement
COUNT - this QUERYTYPE counts the number of rows for a table
DISTINCT - this QUERYTYPE uses the DISTINCT keyword in the SQL statement, avoiding repeating values in a column

USE (for columns):

Special object for this program. Every selected column has a USE.
RETURN - This USE is the column selected. (ex. SELECT braincolumn FROM table)
FILTER - This USE is a column filtered on using where or like statements. (ex. ... WHERE kidneycolumn = '5')

SELECT braincolumn FROM table WHERE kidneycolumn = '5'; In this SQL statement, braincolumn has the RETURN USE, while kidneycolumn has the FILTER USE.

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
            
            # Convert messages to LangChain format
            from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
            langchain_messages = []
            for msg in messages_array:
                if msg["role"] == "system":
                    langchain_messages.append(SystemMessage(content=msg["content"]))
                elif msg["role"] == "user":
                    langchain_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    langchain_messages.append(AIMessage(content=msg["content"]))
            
            # Call AI with tools
            response = await client_with_tools.ainvoke(langchain_messages)
            ai_response = response.content if response.content else ""
            
            # Check if tool was called
            if hasattr(response, 'tool_calls') and response.tool_calls:
                from langchain_core.messages import ToolMessage
                
                # Store original user query for query construction tool
                original_user_query = message.content
                
                # FIRST AI CALL: Execute table info tools in parallel (query_neoxCancerSpecific, query_neoxUniversal)
                tool_messages = []
                for tool_call in response.tool_calls:
                    tool_name = tool_call.get('name')
                    tool_args = tool_call.get('args', {})
                    print(f"🔧 Tool called: {tool_name} with args: {tool_args}")
                    
                    # Route to correct tool (only table info tools in first round)
                    if tool_name == "query_neoxCancerSpecific":
                        tool_result = await query_neoxCancerSpecific.ainvoke(tool_args)
                    elif tool_name == "query_neoxUniversal":
                        tool_result = await query_neoxUniversal.ainvoke(tool_args)
                    else:
                        # Skip query construction tool if called in first round (should be in second round)
                        print(f"⚠️ Skipping {tool_name} in first round - should be called in second round")
                        tool_result = None
                    
                    if tool_result is not None:
                        print(f"📊 Tool {tool_name} result length: {len(str(tool_result))} chars")
                        print(tool_result)
                        tool_message = ToolMessage(content=str(tool_result), tool_call_id=tool_call["id"])
                        tool_messages.append(tool_message)
                
                # Add AI's tool-calling message and all tool results
                langchain_messages.append(response)
                langchain_messages.extend(tool_messages)
                
                # If no tool results were generated, skip second AI call
                if not tool_messages:
                    print("⚠️ No tool results generated, using initial AI response")
                    ai_response = response.content if response.content else "I couldn't process your request. Please try rephrasing."
                else:
                    # Second AI call: AI uses tool results to call query_neoxQueryConstruction or provide final response
                    final_response = await client_with_tools.ainvoke(langchain_messages)
                    
                    sql_query = None
                    if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
                        for tool_call in final_response.tool_calls:
                            tool_name = tool_call.get('name')
                            if tool_name == "query_neoxQueryConstruction":
                                tool_args = tool_call.get('args', {})
                                if "user_query" not in tool_args:
                                    tool_args["user_query"] = original_user_query
                                print(f"🔧 Query construction tool called with args: {tool_args}")
                                sql_query = await query_neoxQueryConstruction.ainvoke(tool_args)
                                print(f"📊 Generated SQL query: {sql_query[:100]}...")
                                break
                    
                    # Use only query_neoxQueryConstruction's result as the final response (ignore AI formatting)
                    if sql_query and sql_query.upper().startswith("SELECT"):
                        ai_response = f"SQL: {sql_query}"
                    elif hasattr(final_response, 'content'):
                        ai_response = final_response.content if final_response.content else ""
                    else:
                        ai_response = str(final_response)
                    
                    if not ai_response or ai_response.strip() == "":
                        print("⚠️ Empty response from second AI call, using tool results")
                        ai_response = "\n\n".join([f"**Tool Result {i+1}:**\n{str(tool_msg.content)}" for i, tool_msg in enumerate(tool_messages)])
            
            # Only use fallback message if we truly have no response
            if not ai_response or ai_response.strip() == "":
                ai_response = "I couldn't generate a response. Please try rephrasing your question or check the console for errors."
            else:
                ai_response = ai_response.strip()
            
            # Update conversation history
            conversation_history.append({"role": "user", "content": message.content})
            conversation_history.append({"role": "assistant", "content": ai_response})
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]
                cl.user_session.set("conversation_history", conversation_history)
        except Exception as e:
            reply = f"❌ Error: {str(e)}"
            await cl.Message(content=reply).send()
            return
        
        # Check if AI returned a SQL query
        if ai_response.startswith("SQL:"):
            sql_query = ai_response[4:].strip()
            if not sql_query.upper().startswith('SELECT'):
                reply = "⚠️ Only SELECT queries are allowed."
            else:
                async with db_pool.acquire() as conn:
                    try:
                        results = await conn.fetch(sql_query)
                        if results:
                            # Build a short summary for the AI to describe (query + row count + sample)
                            n_rows = len(results)
                            col_names = list(results[0].keys())
                            sample = [dict(r) for r in results[:5]]
                            summary_for_ai = (
                                f"SQL executed: {sql_query}\n"
                                f"Rows returned: {n_rows}\n"
                                f"Columns: {col_names}\n"
                                f"Sample (first {len(sample)} rows): {sample}"
                            )
                            describe_messages = [
                                SystemMessage(content="You briefly describe query results for the user. Do not list every row; summarize what the data shows in 2–4 sentences. Mention row count and what the columns/values represent."),
                                HumanMessage(content=summary_for_ai),
                            ]
                            desc_response = await client.ainvoke(describe_messages)
                            description = (desc_response.content or "").strip() or f"The query returned {n_rows} rows."
                            reply = f"**Query:**\n```sql\n{sql_query}\n```\n\n**Results:** {description}"
                        else:
                            reply = f"**Query:**\n```sql\n{sql_query}\n```\n\n✅ The query ran successfully but returned no rows."
                    except Exception as e:
                        reply = f"❌ Error: {str(e)}"
        else:
            reply = ai_response
        
        await cl.Message(content=reply).send()
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"❌ An unexpected error occurred: {str(e)}").send()