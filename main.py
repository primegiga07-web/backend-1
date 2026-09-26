import os
import random
import string
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

class AuthRequest(BaseModel):
    device_id: str
    referred_by: str | None = None

class HypeRequest(BaseModel):
    profile_id: str

def generate_referral_code() -> str:
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def generate_redemption_code() -> str:
    return ''.join(random.choices(string.digits, k=8))

@app.post("/api/auth/anon")
def auth_anon(req: AuthRequest):
    # 1. Check existing device
    existing = supabase.table("profiles").select("*").eq("device_id", req.device_id).execute()
    if existing.data:
        return existing.data[0]

    # 2. Register new profile
    new_user_data = {
        "device_id": req.device_id,
        "referral_code": generate_referral_code(),
        "referred_by": req.referred_by
    }
    inserted = supabase.table("profiles").insert(new_user_data).execute()
    user = inserted.data[0]

    # 3. Check milestone for the referrer
    if req.referred_by:
        # Count how many profiles have this specific referred_by code
        referrals = supabase.table("profiles").select("id", count="exact").eq("referred_by", req.referred_by).execute()
        if referrals.count == 1:
            redemption_code = generate_redemption_code()
            supabase.table("profiles").update({"redemption_code": redemption_code}).eq("referral_code", req.referred_by).execute()

    return user

@app.get("/api/games")
def get_games():
    games = supabase.table("games").select("*").order("created_at", desc=True).execute()
    return games.data

@app.post("/api/games/{game_id}/hype")
def hype_game(game_id: str, req: HypeRequest):
    try:
        # DB Trigger handles the increment automatically
        supabase.table("hypes").insert({"profile_id": req.profile_id, "game_id": game_id}).execute()
        return {"status": "success", "message": "Hype added"}
    except Exception as e:
        # Catch Postgres Unique Violation (already hyped)
        raise HTTPException(status_code=400, detail="Already hyped or invalid data")