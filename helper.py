import psycopg2
import json

# Update with your connection details
conn = psycopg2.connect(
    host="127.0.0.1",
    port=5432,
    dbname="local_postgres_full_test",
    user="haym4b",
    password="magicburger5_"
)
cursor = conn.cursor()

# Step 1: Get all columns except 'uid'
cursor.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'blca_meta'
      AND column_name != 'uid'
    ORDER BY ordinal_position;
""")
columns = [row[0] for row in cursor.fetchall()]

# Step 2: For each column, get distinct non-null values
unique_values = {}
for col in columns:
    cursor.execute(f'SELECT DISTINCT "{col}" FROM blca_meta WHERE "{col}" IS NOT NULL ORDER BY "{col}";')
    values = [row[0] for row in cursor.fetchall()]
    unique_values[col] = values

cursor.close()
conn.close()

# Step 3: Print results
for col, values in unique_values.items():
    print(f"\n{col} ({len(values)} unique values):")
    print(values)

# Optional: save to JSON
with open("blca_meta_unique_values.json", "w") as f:
    json.dump(unique_values, f, indent=2)

print("\nSaved to blca_meta_unique_values.json")