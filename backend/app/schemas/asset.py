from pydantic import BaseModel


class AssetResponse(BaseModel):
    id: str
    name: str
    type: str
    description: str | None = None