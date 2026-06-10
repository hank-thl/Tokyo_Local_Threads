from flask_socketio import SocketIO

try:
    from services.rag_service import RagService
except ImportError:
    from backend.services.rag_service import RagService


def register_chat_socket(socketio: SocketIO) -> None:
    # 建立 RAG 服務實例，讓 Socket 層只負責收送訊息，不直接處理 AI 與資料邏輯。
    rag_service = RagService()

    @socketio.on("connect")
    def handle_connect():
        print("SocketIO client connected")

    @socketio.on("disconnect")
    def handle_disconnect():
        print("SocketIO client disconnected")

    @socketio.on("user_message")
    def handle_user_message(data):
        # 前端預期傳入：
        # {
        #   "session_id": "user-or-browser-session-id",
        #   "message": "使用者問題"
        # }
        payload = data or {}
        session_id = payload.get("session_id") or "default_session"
        message = payload.get("message", "").strip()

        if not message:
            socketio.emit(
                "ai_message",
                {
                    "session_id": session_id,
                    "message": "請輸入想詢問的旅遊需求。",
                },
            )
            return

        answer = rag_service.generate_travel_advice(
            session_id=session_id,
            user_query=message,
        )

        # 回傳 AI 回覆給前端；目前是一次性回覆，後續可改為 streaming。
        socketio.emit(
            "ai_message",
            {
                "session_id": session_id,
                "message": answer,
            },
        )
