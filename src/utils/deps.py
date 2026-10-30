from fastapi import Depends, File, UploadFile
from ..db.db import get_db

file: UploadFile = File(...)
_get_db = Depends(get_db)
