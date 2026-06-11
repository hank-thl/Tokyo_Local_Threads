import re

try:
    import database
except ImportError:
    from backend import database


class SpotRepository:
    # 景點/餐廳文件的資料存取層。
    # PoC 階段資料量小，先使用 PyMongo regex 關鍵字比對，不導入向量資料庫。
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

    def get_relevant_spots(self, user_query: str, limit: int = 8) -> list[dict]:
        # 從使用者問題中取出關鍵字，針對名稱、介紹、AI 背景與 SDG 標籤做簡單比對。
        # 目前 documents 同時包含景點與餐廳，因此方法名稱沿用 spot，但實際會回傳所有旅遊文件。
        if database.documents_collection is None:
            raise RuntimeError("MongoDB collection 尚未初始化")

        keywords = self._extract_keywords(user_query)
        category_filter = self._detect_category_filter(user_query)
        prefers_low_crowd = self._prefers_low_crowd(user_query)
        base_query = {}
        if category_filter:
            base_query["category"] = category_filter
        if prefers_low_crowd:
            base_query["crowd_level"] = {"$lte": 3}

        skip_count = 3 if self._wants_more_options(user_query) else 0

        if not keywords:
            cursor = (
                database.documents_collection.find(base_query)
                .sort([("crowd_level", 1), ("name.zh", 1)])
                .skip(skip_count)
                .limit(limit)
            )
            documents = [self._serialize_document(document) for document in cursor]

            if not documents and prefers_low_crowd and category_filter:
                fallback_cursor = (
                    database.documents_collection.find({"category": category_filter})
                    .sort([("crowd_level", 1), ("name.zh", 1)])
                    .skip(skip_count)
                    .limit(limit)
                )
                documents = [
                    self._serialize_document(document) for document in fallback_cursor
                ]

            return documents

        regex_conditions = []
        for keyword in keywords:
            regex = {"$regex": re.escape(keyword), "$options": "i"}
            regex_conditions.extend(
                [
                    {"name.zh": regex},
                    {"name.jp": regex},
                    {"ui_description.zh": regex},
                    {"ui_description.jp": regex},
                    {"ai_context": regex},
                    {"sdg_tags": regex},
                    {"food_categories": regex},
                ]
            )

        query = {**base_query, "$or": regex_conditions}
        cursor = (
            database.documents_collection.find(query)
            .sort([("crowd_level", 1), ("name.zh", 1)])
            .skip(skip_count)
            .limit(limit)
        )
        documents = [self._serialize_document(document) for document in cursor]

        # 若完全沒有命中，回傳較不擁擠的資料作為保底 Context，避免 LLM 沒有根據可回答。
        if not documents:
            fallback_cursor = (
                database.documents_collection.find(base_query)
                .sort([("crowd_level", 1), ("name.zh", 1)])
                .skip(skip_count)
                .limit(limit)
            )
            documents = [
                self._serialize_document(document) for document in fallback_cursor
            ]

        # 若「人少」條件太嚴導致沒有資料，放寬為同類別資料，但仍依擁擠度排序。
        if not documents and prefers_low_crowd and category_filter:
            fallback_cursor = (
                database.documents_collection.find({"category": category_filter})
                .sort([("crowd_level", 1), ("name.zh", 1)])
                .skip(skip_count)
                .limit(limit)
            )
            documents = [
                self._serialize_document(document) for document in fallback_cursor
            ]

        return documents

    def find_low_crowd_spots_by_tags(
        self,
        sdg_tags: list[str],
        exclude_detail_urls: set[str] | None = None,
        limit: int = 5,
    ) -> list[dict]:
        # 依照相同 SDG 標籤尋找 crowd_level 較低的分流候選。
        # 這是「人潮避雷針」需要的替代推薦資料。
        if database.documents_collection is None:
            raise RuntimeError("MongoDB collection 尚未初始化")

        query: dict = {
            "crowd_level": {"$lte": 3},
        }

        if sdg_tags:
            query["sdg_tags"] = {"$in": sdg_tags}

        if exclude_detail_urls:
            query["detail_url"] = {"$nin": list(exclude_detail_urls)}

        cursor = (
            database.documents_collection.find(query)
            .sort([("crowd_level", 1), ("name.zh", 1)])
            .limit(limit)
        )
        return [self._serialize_document(document) for document in cursor]

    def _extract_keywords(self, user_query: str) -> list[str]:
        # 保留中文、日文、英文與數字關鍵字；過短的英文虛詞不納入查詢。
        tokens = re.findall(r"[\w\u3040-\u30ff\u3400-\u9fff]+", user_query or "")
        stop_words = {
            "我",
            "你",
            "這",
            "想",
            "要",
            "去",
            "請",
            "推薦",
            "附近",
            "可以",
            "嗎",
            "的",
            "有",
            "和",
            "或",
            "and",
            "the",
            "to",
            "人少",
            "一點",
            "肚子餓",
            "台東區",
            "東京",
            "旅遊",
            "餐廳",
            "美食",
            "景點",
            "店家",
            "地點",
            "選擇",
            "比較",
            "只有",
            "三家",
            "其他",
            "更多",
            "別的",
            "低擁擠",
            "避開人潮",
        }

        keywords = []
        for token in tokens:
            normalized = token.strip()
            if not normalized or normalized.lower() in stop_words:
                continue
            if len(normalized) <= 1 and normalized.isascii():
                continue
            if normalized not in keywords:
                keywords.append(normalized)

        return keywords[:8]

    def _detect_category_filter(self, user_query: str) -> str | None:
        food_keywords = {
            "肚子餓",
            "吃",
            "餐廳",
            "美食",
            "料理",
            "午餐",
            "晚餐",
            "甜點",
            "壽司",
            "拉麵",
            "咖啡",
            "小吃",
            "用餐",
            "food",
            "restaurant",
        }
        normalized_query = (user_query or "").lower()
        if any(keyword in normalized_query for keyword in food_keywords):
            return "restaurant"

        return None

    def _prefers_low_crowd(self, user_query: str) -> bool:
        low_crowd_keywords = {
            "人少",
            "不要太擠",
            "不想排隊",
            "避開人潮",
            "安靜",
            "清幽",
            "冷門",
            "少一點",
            "less crowded",
            "quiet",
        }
        normalized_query = (user_query or "").lower()
        return any(keyword in normalized_query for keyword in low_crowd_keywords)

    def _wants_more_options(self, user_query: str) -> bool:
        more_keywords = {
            "只有這三家",
            "只有三家",
            "還有嗎",
            "還有別的",
            "其他",
            "更多",
            "別的",
            "換一批",
            "不是這幾家",
        }
        normalized_query = (user_query or "").lower()
        return any(keyword in normalized_query for keyword in more_keywords)

    def _serialize_document(self, document: dict) -> dict:
        document["_id"] = str(document["_id"])
        return document
