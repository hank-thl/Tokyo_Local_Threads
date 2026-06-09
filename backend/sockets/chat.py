from flask_socketio import SocketIO


def register_chat_socket(socketio: SocketIO) -> None:
    # 預留聊天連線事件。RAG 與 LLM 回覆邏輯會在後續階段補上。
    @socketio.on("connect")
    def handle_connect():
        print("SocketIO client connected")

    @socketio.on("disconnect")
    def handle_disconnect():
        print("SocketIO client disconnected")
