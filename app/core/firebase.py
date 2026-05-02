#app/core/firebase.py
# 
import firebase_admin
from firebase_admin import credentials
from app.core.config import settings

def init_firebase():
    if not firebase_admin._apps:
        private_key = settings.FIREBASE_PRIVATE_KEY.replace('\\n', '\n')
        
        cred = credentials.Certificate({
            "project_id": settings.FIREBASE_PROJECT_ID,
            "private_key_id": settings.FIREBASE_PRIVATE_KEY_ID, # <- Agregado aquí
            "private_key": private_key,
            "client_email": settings.FIREBASE_CLIENT_EMAIL,
            "type": "service_account",
            "token_uri": "https://oauth2.googleapis.com/token"
        })
        
        firebase_admin.initialize_app(cred)
        print("[Firebase] Inicializado correctamente 🔥")

init_firebase()