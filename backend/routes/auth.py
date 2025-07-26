from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import Optional
from services.supabase import supabase
import os

router = APIRouter(prefix="/auth")

# Request/Response Models
class MagicLinkRequest(BaseModel):
    email: EmailStr

class MagicLinkResponse(BaseModel):
    message: str
    email: str

class VerifyOTPRequest(BaseModel):
    email: EmailStr
    token: str

class AuthResponse(BaseModel):
    user_id: str
    email: str
    name: Optional[str] = None
    session_token: str

class LogoutResponse(BaseModel):
    message: str

@router.post("/magic-link", response_model=MagicLinkResponse)
async def send_magic_link(request: MagicLinkRequest):
    """Send magic link to user's email"""
    try:
        # Use standard OTP sign-in method
        auth_response = supabase.auth.sign_in_with_otp({
            "email": request.email,
            "options": {
                "email_redirect_to": f"{os.getenv('FRONTEND_URL', 'http://localhost:8080')}/auth/verify"
            }
        })
        
        print(f"Magic link response: {auth_response}")
        
        return MagicLinkResponse(
            message="Magic link sent to your email",
            email=request.email
        )
        
    except Exception as e:
        print(f"Error sending magic link: {e}")
        # Return a more specific error message
        if "User not allowed" in str(e):
            raise HTTPException(status_code=400, detail="Email authentication not enabled for this user")
        elif "Invalid email" in str(e):
            raise HTTPException(status_code=400, detail="Invalid email address")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to send magic link: {str(e)}")

@router.post("/verify", response_model=AuthResponse)
async def verify_magic_link(request: VerifyOTPRequest):
    """Verify magic link token and create session"""
    try:
        # Verify the OTP token
        auth_response = supabase.auth.verify_otp({
            "email": request.email,
            "token": request.token,
            "type": "magiclink"
        })
        
        if not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        # Get user profile from users table
        try:
            profile_response = supabase.table("users").select("*").eq("email", request.email).execute()
            user_profile = profile_response.data[0] if profile_response.data else None
        except Exception:
            user_profile = None
        
        return AuthResponse(
            user_id=auth_response.user.id,
            email=request.email,
            name=user_profile.get("name") if user_profile else None,
            session_token=auth_response.session.access_token
        )
        
    except Exception as e:
        print(f"Error verifying magic link: {e}")
        if "Invalid token" in str(e) or "expired" in str(e).lower():
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        else:
            raise HTTPException(status_code=500, detail="Failed to verify token")

@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request):
    """Logout user and invalidate session"""
    try:
        # Get session token from request headers
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="No valid session")
        
        token = auth_header.split(" ")[1]
        
        # Sign out the user
        supabase.auth.sign_out()
        
        return LogoutResponse(message="Successfully logged out")
        
    except Exception as e:
        print(f"Error during logout: {e}")
        raise HTTPException(status_code=500, detail="Failed to logout")

@router.get("/me")
async def get_current_user(request: Request):
    """Get current user profile"""
    try:
        # Get session token from request headers
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="No valid session")
        
        token = auth_header.split(" ")[1]
        
        # Get user from token
        user_response = supabase.auth.get_user(token)
        
        if not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid session")
        
        # Get user profile from users table
        try:
            profile_response = supabase.table("users").select("*").eq("email", user_response.user.email).execute()
            user_profile = profile_response.data[0] if profile_response.data else None
        except Exception:
            user_profile = None
        
        return {
            "user_id": user_response.user.id,
            "email": user_response.user.email,
            "name": user_profile.get("name") if user_profile else None
        }
        
    except Exception as e:
        print(f"Error getting current user: {e}")
        raise HTTPException(status_code=401, detail="Invalid session") 

@router.delete("/delete")
async def delete_account(request: Request):
    """Delete the current user from Supabase Auth and users table."""
    try:
        # Get session token from request headers
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="No valid session")
        token = auth_header.split(" ")[1]
        # Get user from token
        user_response = supabase.auth.get_user(token)
        if not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid session")
        user_id = user_response.user.id
        user_email = user_response.user.email
        # Delete from Supabase Auth
        try:
            supabase.auth.admin.delete_user(user_id)
        except Exception as e:
            print(f"Error deleting user from Supabase Auth: {e}")
            raise HTTPException(status_code=500, detail="Failed to delete user from auth")
        # Delete from users table
        try:
            supabase.table("users").delete().eq("email", user_email).execute()
        except Exception as e:
            print(f"Error deleting user from users table: {e}")
            # Not fatal, continue
        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Account deleted successfully"})
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting account: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete account") 

@router.get("/usage")
async def get_usage_stats(request: Request):
    """Return total sessions, total journal entries, and account creation date for the current user."""
    try:
        # Get session token from request headers
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="No valid session")
        token = auth_header.split(" ")[1]
        # Get user from token
        user_response = supabase.auth.get_user(token)
        if not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid session")
        user_id = user_response.user.id
        user_email = user_response.user.email
        # Get account creation date
        created_at = user_response.user.created_at if hasattr(user_response.user, 'created_at') else None
        # Count sessions
        try:
            sessions_resp = supabase.table("sessions").select("*").eq("user_id", user_id).execute()
            total_sessions = len(sessions_resp.data) if sessions_resp.data else 0
        except Exception as e:
            print(f"Error counting sessions: {e}")
            total_sessions = 0
        # Count journal entries
        try:
            entries_resp = supabase.table("journal_entries").select("*").eq("user_id", user_id).execute()
            total_entries = len(entries_resp.data) if entries_resp.data else 0
        except Exception as e:
            print(f"Error counting journal entries: {e}")
            total_entries = 0
        return {
            "total_sessions": total_sessions,
            "total_entries": total_entries,
            "created_at": created_at
        }
    except Exception as e:
        print(f"Error getting usage stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get usage stats") 