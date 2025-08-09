import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from config import DATABASE_URI_SESSIONS_F, LOG_CHANNEL_SESSIONS_FILES
from tenacity import retry, stop_after_attempt, wait_exponential

class Database:
    def __init__(self):
        self.client = MongoClient(
            DATABASE_URI_SESSIONS_F,
            server_api=ServerApi('1'),
            maxPoolSize=100,
            minPoolSize=10,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000
        )
        self.db = self.client['Cluster0']['sessions']
        self._test_connection()

    def _test_connection(self):
        try:
            self.client.admin.command('ping')
            print("✅ Successfully connected to MongoDB!")
        except Exception as e:
            print(f"❌ MongoDB connection error: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def update_user(self, user_id, data):
        return self.db.update_one({"id": user_id}, {"$set": data})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def find_user(self, user_id):
        return self.db.find_one({"id": user_id})

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def disable_promotion(self, phone_number):
        return self.db.update_one(
            {"mobile_number": phone_number},
            {"$set": {"promotion": False}}
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_session(self, user_id, data):
        if existing := await self.find_user(user_id):
            return await self.update_user(user_id, data)
        else:
            data['id'] = user_id
            return self.db.insert_one(data)

# Initialize database instance
db = Database()
