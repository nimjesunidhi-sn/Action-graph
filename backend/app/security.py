import jwt
from datetime import datetime, timedelta, timezone
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.database import get_db
from app.models import User

hasher = PasswordHash.recommended()
oauth = OAuth2PasswordBearer(tokenUrl='/api/auth/login')
def hash_password(password: str) -> str: return hasher.hash(password)
def verify_password(password: str, stored: str) -> bool: return hasher.verify(password, stored)
def make_token(user_id: int) -> str:
    return jwt.encode({'sub': str(user_id), 'exp': datetime.now(timezone.utc)+timedelta(hours=24)}, settings.jwt_secret, algorithm='HS256')
def current_user(token: str = Depends(oauth), db: Session = Depends(get_db)) -> User:
    try: uid = int(jwt.decode(token, settings.jwt_secret, algorithms=['HS256'])['sub'])
    except Exception: raise HTTPException(401, 'Invalid or expired access token')
    user = db.get(User, uid)
    if not user: raise HTTPException(401, 'User no longer exists')
    return user
