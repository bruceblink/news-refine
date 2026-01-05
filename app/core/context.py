from dataclasses import dataclass
from typing import Optional

@dataclass
class UserContext:
    user_id: int
    org_id: Optional[int]
    role: str
