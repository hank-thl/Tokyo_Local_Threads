from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

try:
    from config import Config
except ImportError:
    from backend.config import Config

# 這些變數會在 app 啟動時由 init_db() 初始化。
# 後續 Repository 層會從這裡取得 collection 實例。
client: MongoClient | None = None
db: Database | None = None
documents_collection: Collection | None = None


def init_db(config: Config) -> None:
    global client, db, documents_collection

    if not config.mongodb_uri:
        raise EnvironmentError("請在根目錄 .env 設定 MONGODB_URI")

    # 只建立 MongoDB Atlas 連線實例，不在此撰寫任何查詢邏輯。
    client = MongoClient(config.mongodb_uri, serverSelectionTimeoutMS=10000)
    db = client[config.mongodb_db_name]
    documents_collection = db[config.mongodb_collection_name]
