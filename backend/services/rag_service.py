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

        # 1. 依照使用者問題，先從 MongoDB 找出相關旅遊文件。
        relevant_spots = self.spot_repository.get_relevant_spots(user_query)

        # 2. 若相關文件中有 crowd_level 4 或 5 的熱門點，
        #    額外找出相同 SDG 標籤、但 crowd_level 較低的分流候選。
        diversion_spots = self._find_diversion_spots(relevant_spots)

        # 3. 將 MongoDB 文件整理成 RAG Context，讓 LLM 只能依據這些資料回答。
        context = self._build_rag_context(relevant_spots, diversion_spots)

        # 4. 建立具備專題核心規則的 System Prompt。
        system_prompt = self._build_system_prompt(context)

        # 5. 呼叫 Gemini。此處使用既有 GOOGLE_API_KEY / GEMINI_API_KEY。
        llm = self._get_llm()
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
8. 回覆格式必須清楚分段，請使用以下結構：
   - 先用 1 句話直接回答使用者需求。
   - 接著列出 2 到 3 個推薦項目，每個項目都用「### 名稱」作為小標題，名稱必須完全使用 RAG 大抄脈絡中的「景點/店家名稱」。
   - 每個推薦項目下方用短行列出「推薦理由」、「永續標籤」、「擁擠度」。
   - 若需要分流，新增「### 觀光人潮避雷針」段落。
   - 最後用 1 句話詢問使用者下一步偏好。
9. 不要把所有內容寫成同一段；每個段落之間必須保留換行。

RAG 大抄脈絡：
{context}
""".strip()

    def _normalize_crowd_level(self, spot: dict) -> int:
        try:
            level = int(spot.get("crowd_level", 3))
        except (TypeError, ValueError):
            return 3

        return max(1, min(5, level))
