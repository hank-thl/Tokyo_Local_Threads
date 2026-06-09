try:
    from repositories.spot_repository import SpotRepository
except ImportError:
    from backend.repositories.spot_repository import SpotRepository


class RagService:
    # RAG 核心服務層。
    # 目前先作為 API 與 Repository 的中介，RAG 邏輯後續再補。
    def __init__(self, spot_repository: SpotRepository | None = None):
        self.spot_repository = spot_repository or SpotRepository()

    def list_documents(
        self, category: str | None = None, limit: int = 20
    ) -> list[dict]:
        return self.spot_repository.find_documents(category=category, limit=limit)

    def list_sdg_tags(self) -> list[str]:
        return self.spot_repository.find_sdg_tags()
