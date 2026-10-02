# fix_49a_01
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class Doc:
    """Один документ в описи. Дело = группа Doc с общим case_number."""
    title: str
    prefix: str
    case_number: int
    year: int
    pages_count: int = 1
    row_id: Optional[int] = None
    row_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "row_id": self.row_id,
            "row_index": self.row_index,
            "title": self.title,
            "prefix": self.prefix,
            "case_number": self.case_number,
            "year": self.year,
            "pages_count": self.pages_count,
        }
