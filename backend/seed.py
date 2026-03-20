import asyncio
import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from app.libs.database import db_service

# Load environment variables
load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

USERS = [
    # ---- ADMINS ----
    {"user_id": "admin-001", "username": "admin-001", "role": "admin", "password": "Admin@001"},
    {"user_id": "admin-002", "username": "admin-002", "role": "admin", "password": "Admin@002"},
    # ---- STUDENTS ----
    {"user_id": "student-001", "username": "student-001", "role": "student", "password": "Student@001"},
    {"user_id": "student-002", "username": "student-002", "role": "student", "password": "Student@002"},
]

async def init_schema():
    """Reads schema.sql and creates tables in the database."""
    print("🔄 Initializing Database Schema...")
    
    # Locate schema.sql relative to this script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(base_dir, "schema.sql")

    if not os.path.exists(schema_path):
        print(f"❌ Error: schema.sql not found at {schema_path}")
        return

    # Read the SQL file
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    # Execute it
    async with db_service.pool.acquire() as conn:
        await conn.execute(schema_sql)
    
    print("✅ Tables created successfully.")

async def seed_data():
    # 1. Connect to DB
    if not db_service.pool:
        await db_service.init_db()

    # 2. RUN SCHEMA FIRST
    await init_schema()

    # 3. Insert Users
    print("🔄 Seeding Users...")
    for user in USERS:
        password_hash = pwd_context.hash(user["password"])
        
        # ✅ Check if user exists
        try:
            existing = await db_service.get_user_by_username(user["username"])
            if existing:
                print(f"   ⏭️  Skipped existing: {user['username']}")
                continue
        except:
            pass
        
        # ✅ Create new user
        try:
            await db_service.create_user(
                user_id=user["user_id"],
                username=user["username"],
                role=user["role"],
                password_hash=password_hash,
            )
            print(f"   ✅ Added user: {user['username']} (role: {user['role']})")
        except Exception as e:
            print(f"   ❌ Error creating {user['username']}: {e}")

    print("✅ Database seeding completed!")

if __name__ == "__main__":
    asyncio.run(seed_data())
