# app/utils.py
from typing import Any, Dict, Optional

def to_id(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convierte _id -> id (str). Si doc es None, devuelve {}.
    Útil para content-type dinámico en respuestas internas.
    """
    if doc is None:
        return {}
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d
