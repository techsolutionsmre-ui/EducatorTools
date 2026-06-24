import os
import shutil
import tempfile
import asyncio
import secrets
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
import fitz

import config
import database
import converter
import email_service

# Initialize database tables
database.init_db()

app = FastAPI(title="EducatorTools API")

# Configure CORS for local development when React runs on port 5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Concurrency Semaphore to prevent OCI CPU choking
conversion_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_CONVERSIONS)

# Pydantic Schemas
class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    profession: str

class VerifyEmailSchema(BaseModel):
    email: EmailStr
    code: str

class ResendVerificationSchema(BaseModel):
    email: EmailStr

class UserResponse(BaseModel):
    email: str
    profession: str
    status: str
    email_verified: bool

class BillingInfoResponse(BaseModel):
    price_zar: int
    billing_period: str
    admin_email: str
    default_package_id: str
    packages: list[dict]

class CreditDetailsResponse(BaseModel):
    message: str
    email_sent: bool

# Helper: JWT Operations
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    return encoded_jwt

def generate_verification_code():
    return f"{secrets.randbelow(1000000):06d}"

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = database.get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user

async def get_active_user(current_user = Depends(get_current_user)):
    status_val = current_user["status"]
    if status_val not in ["active", "trial"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is pending EFT subscription activation or has been suspended."
        )
    if status_val == "trial":
        conversions = database.get_user_conversions(current_user["id"])
        successful_trials = len([c for c in conversions if c["status"] == "success"])
        if successful_trials >= 3:
            database.update_user_status(current_user["id"], 'pending')
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Free trial exhausted. Account is pending admin approval."
            )
    return current_user

# --- AUTH ENDPOINTS ---

@app.post("/api/auth/register")
def register(user_data: RegisterSchema):
    if not user_data.email or not user_data.password:
        raise HTTPException(status_code=400, detail="Email and password required.")
        
    email_clean = user_data.email.strip().lower()
    if "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Invalid email format.")

    # Check if user already exists
    existing = database.get_user_by_email(email_clean)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered.")
        
    verification_code = generate_verification_code()
    success = database.create_user(email_clean, user_data.password, user_data.profession, verification_code)
    if not success:
        raise HTTPException(status_code=500, detail="Error creating account.")

    email_sent = email_service.send_verification_code(email_clean, verification_code)
    email_service.notify_admin_new_registration(email_clean, user_data.profession)
        
    return {
        "message": "Account created. Please verify your email before signing in.",
        "requires_verification": True,
        "email_sent": email_sent
    }

@app.post("/api/auth/verify-email")
def verify_email(payload: VerifyEmailSchema):
    code = payload.code.strip()
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(status_code=400, detail="Enter the 6-digit verification code.")

    if not database.verify_email_code(payload.email, code):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code.")

    return {"message": "Email verified. You can now sign in."}

@app.post("/api/auth/resend-verification")
def resend_verification(payload: ResendVerificationSchema):
    user = database.get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found.")

    if user["email_verified"]:
        return {"message": "This email is already verified."}

    verification_code = generate_verification_code()
    if not database.set_verification_code(payload.email, verification_code):
        raise HTTPException(status_code=500, detail="Could not create a new verification code.")

    email_sent = email_service.send_verification_code(payload.email, verification_code)
    return {"message": "A new verification code has been sent.", "email_sent": email_sent}

@app.post("/api/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = database.get_user_by_email(form_data.username)
    if not user or not database.verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user["profession"] != "Admin" and not user["email_verified"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please enter the verification code sent to your email."
        )
        
    access_token = create_access_token(data={"sub": user["email"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user = Depends(get_current_user)):
    return {
        "email": current_user["email"],
        "profession": current_user["profession"],
        "status": current_user["status"],
        "email_verified": bool(current_user["email_verified"])
    }

@app.get("/api/billing/info", response_model=BillingInfoResponse)
def get_billing_info(current_user = Depends(get_current_user)):
    if current_user["profession"] != "Admin" and not current_user["email_verified"]:
        raise HTTPException(status_code=403, detail="Verify your email first.")

    return {
        "price_zar": config.SUBSCRIPTION_PRICE_ZAR,
        "billing_period": "monthly",
        "admin_email": config.ADMIN_EMAIL,
        "default_package_id": config.DEFAULT_PACKAGE_ID,
        "packages": config.PACKAGES,
    }

@app.post("/api/billing/request-credit-details", response_model=CreditDetailsResponse)
def request_credit_details(current_user = Depends(get_current_user)):
    if current_user["profession"] != "Admin" and not current_user["email_verified"]:
        raise HTTPException(status_code=403, detail="Verify your email first.")

    email_sent = email_service.send_credit_details(current_user["email"])
    return {
        "message": "Conversion credit details have been emailed to your registered email address.",
        "email_sent": email_sent,
    }

# --- CONVERTER ENDPOINTS ---

def cleanup_files(paths: list):
    """Background task to remove temporary files immediately after download."""
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"Cleaned up temp file: {path}")
        except Exception as e:
            print(f"Error during file cleanup: {str(e)}")

@app.post("/api/convert")
async def convert_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user = Depends(get_active_user)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Acquire lock (only 1 conversion happens on the server at any given time)
    async with conversion_semaphore:
        # Create temp files safely
        temp_dir = tempfile.gettempdir()
        temp_pdf = os.path.join(temp_dir, f"upload_{os.urandom(8).hex()}.pdf")
        temp_docx = os.path.join(temp_dir, f"converted_{os.urandom(8).hex()}.docx")
        
        try:
            # Write uploaded file to temp disk
            with open(temp_pdf, "wb") as f:
                shutil.copyfileobj(file.file, f)
            
            # Record size
            file_size = os.path.getsize(temp_pdf)

            # Page Pre-Verification
            try:
                doc = fitz.open(temp_pdf)
                page_count = len(doc)
                doc.close()
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid PDF file structure.")

            if current_user["status"] == "trial" and page_count > 4:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Free trial limit exceeded: Trial uploads are limited to a maximum of 4 pages. Please subscribe to convert longer documents."
                )

            if current_user["status"] == "active":
                package = next(
                    (item for item in config.PACKAGES if item["id"] == config.DEFAULT_PACKAGE_ID),
                    config.PACKAGES[0],
                )
                usage = database.get_user_monthly_usage(current_user["id"])
                next_page_count = usage["page_count"] + page_count
                if next_page_count > package["monthly_pages"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=(
                            f"Monthly package limit reached. {package['name']} includes "
                            f"{package['monthly_pages']} pages per month."
                        )
                    )
            
            # Run local conversion synchronously (it runs in thread-safe blocker)
            # Run in executor if necessary, but uvicorn handles async blocking routes smoothly
            page_count = await asyncio.to_thread(converter.convert_pdf_to_docx, temp_pdf, temp_docx)
            
            # Log success in SQLite
            database.add_conversion(
                user_id=current_user["id"],
                filename=file.filename,
                page_count=page_count,
                file_size=file_size,
                status="success"
            )

            # Automatic Status Transition
            if current_user["status"] == "trial":
                trial_conversions = database.get_user_conversions(current_user["id"])
                successful_trials = len([c for c in trial_conversions if c["status"] == "success"])
                if successful_trials >= 3:
                    database.update_user_status(current_user["id"], 'pending')
            
            # Queue files for deletion after response streams back
            background_tasks.add_task(cleanup_files, [temp_pdf, temp_docx])
            
            # Stream converted Word file back as download
            return FileResponse(
                path=temp_docx,
                filename=file.filename.replace(".pdf", ".docx").replace(".PDF", ".docx"),
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
        except HTTPException as http_ex:
            cleanup_files([temp_pdf, temp_docx])
            raise http_ex
        except Exception as e:
            # Log failure in SQLite
            try:
                database.add_conversion(
                    user_id=current_user["id"],
                    filename=file.filename,
                    page_count=0,
                    file_size=0,
                    status="failed"
                )
            except Exception:
                pass
                
            # Clean up temp files immediately on error
            cleanup_files([temp_pdf, temp_docx])
            raise HTTPException(status_code=500, detail=f"Conversion failed: {str(e)}")

@app.get("/api/history")
def get_history(current_user = Depends(get_current_user)):
    return database.get_user_conversions(current_user["id"])

# --- ADMIN ENDPOINTS ---

@app.get("/api/admin/users")
def get_admin_users(current_user = Depends(get_current_user)):
    if current_user["profession"] != "Admin":
        raise HTTPException(status_code=403, detail="Admin permissions required.")
    return database.list_all_users()

@app.post("/api/admin/status/{user_id}")
def update_status(user_id: int, status: str, current_user = Depends(get_current_user)):
    if current_user["profession"] != "Admin":
        raise HTTPException(status_code=403, detail="Admin permissions required.")
        
    if status not in ["pending", "active", "suspended"]:
        raise HTTPException(status_code=400, detail="Invalid status value.")
        
    success = database.update_user_status(user_id, status)
    if not success:
        raise HTTPException(status_code=404, detail="User not found.")
        
    return {"message": f"User status updated to {status} successfully."}

# --- STATIC FILES HOSTING (React SPA routing) ---

# Check if static directory exists (where production built React files reside)
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")
    
    @app.get("/{catchall:path}")
    def serve_spa(catchall: str):
        # Serve index.html for all non-API paths (standard SPA fallback routing)
        if catchall.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found.")
        index_path = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Frontend assets index.html not found.")
else:
    @app.get("/")
    def read_root():
        return {"message": "FastAPI Server Running. Frontend static dir not found. Build React app and check path."}
