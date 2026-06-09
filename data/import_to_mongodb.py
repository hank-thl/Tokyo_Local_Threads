import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

try:
    from pipeline_paths import FINAL_DOCUMENTS_PATH, SCRIPT_DIR
except ImportError:
    from data.pipeline_paths import FINAL_DOCUMENTS_PATH, SCRIPT_DIR

ENV_PATH = os.path.join(SCRIPT_DIR, "..", ".env")
DEFAULT_DB_NAME = "tokyo_local_threads"
DEFAULT_COLLECTION_NAME = "documents"


def load_documents() -> list[dict]:
    with open(FINAL_DOCUMENTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_mongo_config() -> tuple[str, str, str]:
    load_dotenv(ENV_PATH)

    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise EnvironmentError("請在 .env 設定 MONGODB_URI")

    db_name = os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)
    collection_name = os.environ.get(
        "MONGODB_COLLECTION_NAME", DEFAULT_COLLECTION_NAME
    )
    return uri, db_name, collection_name


def build_upsert_operations(documents: list[dict]) -> list[UpdateOne]:
    now = datetime.now(timezone.utc)
    operations = []

    for document in documents:
        detail_url = document.get("detail_url")
        if not detail_url:
            continue

        mongo_document = {
            **document,
            "updated_at": now,
        }

        operations.append(
            UpdateOne(
                {"detail_url": detail_url},
                {
                    "$set": mongo_document,
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
        )

    return operations


def main() -> None:
    uri, db_name, collection_name = get_mongo_config()
    documents = load_documents()
    operations = build_upsert_operations(documents)

    if not operations:
        print("沒有可匯入的文件，請確認 raw_documents.json 是否有 detail_url。")
        return

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)

    try:
        client.admin.command("ping")
        collection = client[db_name][collection_name]
        collection.create_index("detail_url", unique=True)
        collection.create_index("category")
        collection.create_index("sdg_tags")
        collection.create_index("food_categories")

        result = collection.bulk_write(operations, ordered=False)
        print("MongoDB Atlas 匯入完成")
        print(f"資料庫：{db_name}")
        print(f"Collection：{collection_name}")
        print(f"讀取文件：{len(documents)}")
        print(f"送出 upsert：{len(operations)}")
        print(f"新增：{result.upserted_count}")
        print(f"更新：{result.modified_count}")

    except PyMongoError as e:
        raise RuntimeError(f"MongoDB 匯入失敗：{e}") from e
    finally:
        client.close()


if __name__ == "__main__":
    main()
