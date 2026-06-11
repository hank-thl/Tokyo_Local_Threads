import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# LangChain 舊版文件會從 langchain_community 匯入；新版已拆到 langchain_mongodb。
try:
    from langchain_community.chat_message_histories import MongoDBChatMessageHistory
except ImportError:
    from langchain_mongodb.chat_message_histories import MongoDBChatMessageHistory

try:
    from config import load_config
    from repositories.spot_repository import SpotRepository
except ImportError:
    from backend.config import load_config
    from backend.repositories.spot_repository import SpotRepository


class RagService:
    # RAG 核心服務層。
    # 負責整合 MongoDB 檢索、對話歷史、Prompt 組裝與 LLM 生成。
    def __init__(self, spot_repository: SpotRepository | None = None):
        self.spot_repository = spot_repository or SpotRepository()
        self.config = load_config()
        self.last_sources: list[dict] = []
        self.last_recommendations: list[dict] = []

    def list_documents(
        self, category: str | None = None, limit: int = 20
    ) -> list[dict]:
        return self.spot_repository.find_documents(category=category, limit=limit)

    def list_sdg_tags(self) -> list[str]:
        return self.spot_repository.find_sdg_tags()

    def generate_travel_advice(self, session_id: str, user_query: str) -> str:
        # 先建立對話歷史並取得既有訊息。
        # 使用者訊息會在 LLM 呼叫前先寫入，避免 AI 失敗時完全沒有監控紀錄。
        history = self._get_chat_history(session_id)
        previous_messages = history.messages
        history.add_user_message(user_query)

        # 1. 先用 LLM Query Rewriter 將多輪對話整理成適合檢索的明確查詢。
        # 例如「我肚子餓」後接「想要人少一點」會被改寫成
        # 「台東區 人少 避開人潮 餐廳 美食」這類可被 MongoDB regex 命中的查詢。
        llm = self._get_llm()
        retrieval_query = self._rewrite_retrieval_query(
            llm=llm,
            user_query=user_query,
            previous_messages=previous_messages,
        )
        relevant_spots = self.spot_repository.get_relevant_spots(retrieval_query)
        relevant_spots = self._dedupe_restaurant_brands(relevant_spots)

        # 2. 若相關文件中有 crowd_level 4 或 5 的熱門點，
        #    額外找出相同 SDG 標籤、但 crowd_level 較低的分流候選。
        diversion_spots = self._find_diversion_spots(relevant_spots)
        self.last_sources = self._build_sources(relevant_spots + diversion_spots)
        self.last_recommendations = self._build_recommendations(relevant_spots)

        # 3. 將 MongoDB 文件整理成 RAG Context，讓 LLM 只能依據這些資料回答。
        context = self._build_rag_context(relevant_spots, diversion_spots)

        # 4. 建立具備專題核心規則的 System Prompt。
        system_prompt = self._build_system_prompt(context)

        # 5. 呼叫 Gemini。此處使用既有 GOOGLE_API_KEY / GEMINI_API_KEY。
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                *previous_messages,
                HumanMessage(content=user_query),
            ]
        )
        answer = response.content.strip()

        # 6. 將 AI 回覆存入 MongoDB chat_histories。
        history.add_ai_message(answer)

        return answer

    def get_last_sources(self) -> list[dict]:
        return self.last_sources

    def get_last_recommendations(self) -> list[dict]:
        return self.last_recommendations

    def _get_chat_history(self, session_id: str) -> MongoDBChatMessageHistory:
        # 使用 session_id 將每位使用者的多輪對話存在獨立歷史紀錄中。
        return MongoDBChatMessageHistory(
            connection_string=self.config.mongodb_uri,
            database_name="tokyo_local_threads",
            collection_name="chat_histories",
            session_id=session_id,
        )

    def _get_llm(self) -> ChatGoogleGenerativeAI:
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("請在 .env 設定 GOOGLE_API_KEY 或 GEMINI_API_KEY")

        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash-lite",
            google_api_key=api_key,
            temperature=0.4,
        )

    def _build_retrieval_query(self, user_query: str, previous_messages: list) -> str:
        recent_human_messages = []
        for message in previous_messages[-6:]:
            if getattr(message, "type", "") == "human" and message.content:
                recent_human_messages.append(message.content)

        return " ".join([*recent_human_messages, user_query]).strip()

    def _rewrite_retrieval_query(
        self,
        llm: ChatGoogleGenerativeAI,
        user_query: str,
        previous_messages: list,
    ) -> str:
        fallback_query = self._build_retrieval_query(user_query, previous_messages)
        dialogue = self._format_recent_dialogue(previous_messages, user_query)

        rewrite_prompt = f"""
你是 RAG 系統的「查詢改寫器」，不是聊天助理。
請根據最近對話，把使用者真正想找的東京台東區旅遊需求，改寫成一行適合 MongoDB 關鍵字檢索的繁體中文查詢。

改寫規則：
1. 只能輸出查詢文字，不要回答使用者，不要加標點說明。
2. 必須保留使用者提到的地名、店名、景點名、料理類型、SDG 偏好與擁擠度偏好。
3. 若使用者想吃、肚子餓、找美食，查詢中要包含「餐廳 美食」。
4. 若使用者想逛、拍照、文化體驗，查詢中要包含「景點 文化體驗」。
5. 若使用者想人少、安靜、避開排隊，查詢中要包含「人少 避開人潮 低擁擠」。
6. 若當前句子很短，必須承接前文補足需求。
7. 長度控制在 60 個中文字以內。

最近使用者訊息：
{dialogue}
""".strip()

        try:
            response = llm.invoke([HumanMessage(content=rewrite_prompt)])
            rewritten_query = response.content.strip().splitlines()[0].strip()
        except Exception as error:
            print(f"[RAG] Query rewrite failed, fallback to raw query: {error}")
            return fallback_query

        if not rewritten_query:
            return fallback_query

        print(f"[RAG] rewritten query: {rewritten_query}")
        return rewritten_query

    def _format_recent_dialogue(self, previous_messages: list, user_query: str) -> str:
        dialogue_lines = []
        for message in previous_messages[-6:]:
            if getattr(message, "type", "") != "human":
                continue

            content = (message.content or "").strip()
            if content:
                dialogue_lines.append(f"使用者：{content}")

        dialogue_lines.append(f"使用者：{user_query}")
        return "\n".join(dialogue_lines)

    def _find_diversion_spots(self, relevant_spots: list[dict]) -> list[dict]:
        high_crowd_spots = [
            spot for spot in relevant_spots if self._normalize_crowd_level(spot) >= 4
        ]
        if not high_crowd_spots:
            return []

        sdg_tags = []
        excluded_urls = set()
        for spot in high_crowd_spots:
            excluded_urls.add(spot.get("detail_url", ""))
            for tag in spot.get("sdg_tags", []):
                if tag not in sdg_tags:
                    sdg_tags.append(tag)

        return self.spot_repository.find_low_crowd_spots_by_tags(
            sdg_tags=sdg_tags,
            exclude_detail_urls=excluded_urls,
            limit=5,
        )

    def _build_rag_context(
        self,
        relevant_spots: list[dict],
        diversion_spots: list[dict],
    ) -> str:
        if not relevant_spots:
            return "目前資料庫沒有找到可用的景點或餐廳資料。"

        context_blocks = ["【使用者問題命中的資料】"]
        for index, spot in enumerate(relevant_spots, start=1):
            context_blocks.append(self._format_spot_context(index, spot))

        if diversion_spots:
            context_blocks.append("\n【人潮避雷針分流候選】")
            for index, spot in enumerate(diversion_spots, start=1):
                context_blocks.append(self._format_spot_context(index, spot))

        return "\n".join(context_blocks)

    def _dedupe_restaurant_brands(self, spots: list[dict]) -> list[dict]:
        deduped_spots = []
        seen_brands = set()

        for spot in spots:
            if spot.get("category") != "restaurant":
                deduped_spots.append(spot)
                continue

            name = spot.get("name", {})
            display_name = name.get("zh") or name.get("jp") or ""
            brand_key = self._normalize_restaurant_brand(display_name)
            if brand_key and brand_key in seen_brands:
                continue

            if brand_key:
                seen_brands.add(brand_key)
            deduped_spots.append(spot)

        return deduped_spots

    def _format_spot_context(self, index: int, spot: dict) -> str:
        name = spot.get("name", {})
        description = spot.get("ui_description", {})
        sdg_tags = "、".join(spot.get("sdg_tags", [])) or "無"
        crowd_level = self._normalize_crowd_level(spot)
        crowd_reason = spot.get("crowd_reason") or "無"

        return (
            f"{index}. 景點/店家名稱：{name.get('zh', '未命名')}\n"
            f"   日文名稱：{name.get('jp', '無')}\n"
            f"   中文介紹：{description.get('zh', '無')}\n"
            f"   永續標籤：{sdg_tags}\n"
            f"   擁擠度：{crowd_level}/5\n"
            f"   擁擠原因：{crowd_reason}\n"
        )

    def _build_sources(self, spots: list[dict]) -> list[dict]:
        sources = []
        seen_ids = set()

        for spot in spots:
            spot_id = spot.get("_id")
            if not spot_id or spot_id in seen_ids:
                continue

            seen_ids.add(spot_id)
            sources.append(
                {
                    "id": spot_id,
                    "name": spot.get("name", {}),
                    "category": spot.get("category", ""),
                }
            )

        return sources

    def _build_recommendations(self, spots: list[dict], limit: int = 3) -> list[dict]:
        recommendations = []
        seen_ids = set()
        seen_brands = set()

        for spot in spots:
            if spot.get("category") != "restaurant":
                continue

            spot_id = spot.get("_id")
            if not spot_id or spot_id in seen_ids:
                continue

            name = spot.get("name", {})
            display_name = name.get("zh") or name.get("jp") or "未命名店家"
            brand_key = self._normalize_restaurant_brand(display_name)
            if brand_key in seen_brands:
                continue

            seen_ids.add(spot_id)
            seen_brands.add(brand_key)
            description = spot.get("ui_description", {})
            recommendations.append(
                {
                    "id": spot_id,
                    "name": display_name,
                    "name_jp": name.get("jp", ""),
                    "reason": self._build_recommendation_reason(description),
                    "sdg_tags": spot.get("sdg_tags", []),
                    "crowd_level": self._normalize_crowd_level(spot),
                    "crowd_reason": spot.get("crowd_reason", ""),
                }
            )

            if len(recommendations) >= limit:
                break

        return recommendations

    def _normalize_restaurant_brand(self, name: str) -> str:
        brand = name.strip()
        branch_suffixes = [
            "御徒町店",
            "湯島店",
            "上野店",
            "浅草店",
            "淺草店",
            "雷門店",
            "本店",
            "駅前店",
            "車站前店",
            "總店",
        ]

        for suffix in branch_suffixes:
            if brand.endswith(suffix):
                brand = brand[: -len(suffix)].strip()

        return brand.replace(" ", "").replace("　", "").lower()

    def _build_recommendation_reason(self, description: dict) -> str:
        reason = description.get("zh", "").strip()
        if not reason:
            return "可作為台東區在地美食體驗選擇。"

        reason = " ".join(reason.split())
        first_sentence = self._first_sentence(reason)
        if 24 <= len(first_sentence) <= 90:
            return first_sentence

        if len(reason) <= 90:
            return reason

        return f"{reason[:90]}..."

    def _first_sentence(self, text: str) -> str:
        sentence_marks = ["。", "！", "？", "!", "?"]
        end_positions = [
            text.find(mark) + 1 for mark in sentence_marks if text.find(mark) != -1
        ]
        if not end_positions:
            return text

        return text[: min(end_positions)].strip()

    def _build_system_prompt(self, context: str) -> str:
        return f"""
你是「共生東京永續旅遊管家」，服務目標是協助旅客在東京台東區周邊進行更永續、更分流、更尊重在地社區的旅行。

請嚴格遵守以下規則：
1. 只能根據下方「RAG 大抄脈絡」回答，不可以憑空編造資料庫沒有的景點、餐廳、交通或營業資訊。
2. 回答必須使用繁體中文，語氣自然、像專業但親切的在地旅遊管家。
3. 必須主動運用 SDG 標籤說明推薦理由，例如支持在地經濟、歷史建築保存、傳統工藝傳承、在地飲食文化等。
4. 必須考量 crowd_level。若使用者提到或想去的景點/店家 crowd_level 為 4 或 5，回答中必須出現「觀光人潮避雷針」段落。
5. 啟動「觀光人潮避雷針」時，必須清楚提醒該地點較擁擠，並根據相同或相近 sdg_tags，從「人潮避雷針分流候選」中推薦較不擁擠的替代景點。
6. 如果 RAG 大抄脈絡沒有足夠資料回答，請明確說明目前資料不足，並改用已提供的資料做保守建議。
7. 不要輸出資料庫內沒有的價格、精確營業時間、即時排隊狀況或交通細節。
8. crowd_level 是資料推估，不是即時人流；請避免保證「一定不擠」，改用「依資料推估」、「建議避開尖峰」等保守措辭。
9. 若使用者在多輪對話中補充偏好，例如「想要人少一點」、「想吃甜點」、「不要太遠」，請承接上一輪需求，不要像第一次回答一樣重講完整介紹。
10. 推薦理由必須短，單一項目最多 1 句、45 字以內。不要直接貼上完整介紹。
11. 若使用者要求「人少一點」，但 RAG 大抄中最低擁擠度仍是 3/5，請明確說「目前命中資料多為 3/5，我會優先選非地標型、較適合避開尖峰的店家」。
12. 回覆格式必須清楚分段，請使用以下結構：
   - 先用 1 句話直接回答使用者需求。
   - 接著列出 2 到 3 個推薦項目，每個項目都用「### 名稱」作為小標題，名稱必須完全使用 RAG 大抄脈絡中的「景點/店家名稱」。
   - 每個推薦項目下方用短行列出「擁擠度」、「推薦理由」、「永續標籤」。
   - 若需要分流，新增「### 觀光人潮避雷針」段落。
   - 最後用 1 句話詢問使用者下一步偏好。
13. 不要把所有內容寫成同一段；每個段落之間必須保留換行。

RAG 大抄脈絡：
{context}
""".strip()

    def _normalize_crowd_level(self, spot: dict) -> int:
        try:
            level = int(spot.get("crowd_level", 3))
        except (TypeError, ValueError):
            return 3

        return max(1, min(5, level))
