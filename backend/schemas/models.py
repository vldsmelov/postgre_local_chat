from pydantic import BaseModel
from typing import List


class ModelsListResponse(BaseModel):
    models: List[str]
