from fastapi import Depends
from .db import get_db
from sqlalchemy.orm import Session

def db_dep(db: Session = Depends(get_db)):
    return db
