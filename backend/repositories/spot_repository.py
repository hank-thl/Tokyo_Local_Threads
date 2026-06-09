try:
    import database
except ImportError:
    from backend import database


class SpotRepository:
    # 景點/餐廳文件的資料存取層。
    # 目前先提供最小可行的 documents 列表查詢。
    def find_documents(self, category: str | None = None, limit: int = 20) -> list[dict]:
        if database.documents_collection is None:
            raise RuntimeError("MongoDB collection 尚未初始化")

        query = {}
        if category:
            query["category"] = category

        cursor = database.documents_collection.find(query).limit(limit)
        return [self._serialize_document(document) for document in cursor]

    def find_sdg_tags(self) -> list[str]:
        if database.documents_collection is None:
            raise RuntimeError("MongoDB collection 尚未初始化")

        tags = database.documents_collection.distinct("sdg_tags")
        return sorted(tag for tag in tags if tag)

    def _serialize_document(self, document: dict) -> dict:
        document["_id"] = str(document["_id"])
        return document
