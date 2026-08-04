from .service import GenerationService


def create_generation_service() -> GenerationService:
    return GenerationService()
