import os
import shutil
import tempfile
import asyncio
import secrets
import base64
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
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
    package_id: Optional[str] = None
    billing_period_starts_at: Optional[str] = None
    expires_at: Optional[str] = None

class BillingInfoResponse(BaseModel):
    price_zar: int
    billing_period: str
    admin_email: str
    default_package_id: str
    packages: list[dict]

class CreditDetailsResponse(BaseModel):
    message: str
    email_sent: bool

class ActivateSubscriptionSchema(BaseModel):
    package_id: str
    paid_until: Optional[str] = None
    admin_note: Optional[str] = None

# Helper: JWT Operations
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
    return encoded_jwt

def generate_verification_code():
    return f"{secrets.randbelow(1000000):06d}"

def get_package(package_id: str | None):
    return next(
        (item for item in config.PACKAGES if item["id"] == package_id),
        next((item for item in config.PACKAGES if item["id"] == config.DEFAULT_PACKAGE_ID), config.PACKAGES[0]),
    )

def parse_datetime(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

def parse_paid_until(value: str | None):
    if not value:
        return datetime.utcnow() + timedelta(days=30)
    try:
        if len(value) == 10:
            return datetime.fromisoformat(f"{value}T23:59:59")
        return datetime.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid paid-until date.")

def ensure_subscription_current(user):
    if user["status"] != "active" or user["profession"] == "Admin":
        return user

    expires_at = parse_datetime(user["expires_at"])
    if not expires_at or expires_at <= datetime.utcnow():
        database.expire_subscription(user["id"])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Monthly EFT subscription has expired. Please request credit details and renew your account."
        )
    return user

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
    current_user = ensure_subscription_current(current_user)
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
    if current_user["profession"] != "Admin" and current_user["status"] == "active":
        try:
            current_user = ensure_subscription_current(current_user)
        except HTTPException:
            current_user = database.get_user_by_id(current_user["id"])
    return {
        "email": current_user["email"],
        "profession": current_user["profession"],
        "status": current_user["status"],
        "email_verified": bool(current_user["email_verified"]),
        "package_id": current_user["package_id"],
        "billing_period_starts_at": current_user["billing_period_starts_at"],
        "expires_at": current_user["expires_at"],
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
    database.record_credit_details_request(current_user["id"])
    email_service.notify_admin_credit_details_requested(current_user["email"])
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

def get_pdf_tool_limit_bytes():
    return config.MAX_PDF_TOOL_FILE_MB * 1024 * 1024

def get_pdf_merge_limit_bytes():
    return config.MAX_PDF_MERGE_TOTAL_MB * 1024 * 1024

def validate_pdf_upload(file: UploadFile):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

def save_upload_to_temp(file: UploadFile, prefix: str, max_bytes: int):
    validate_pdf_upload(file)
    temp_path = os.path.join(tempfile.gettempdir(), f"{prefix}_{os.urandom(8).hex()}.pdf")
    total = 0
    try:
        with open(temp_path, "wb") as output:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"PDF is too large. Limit is {max_bytes // (1024 * 1024)}MB."
                    )
                output.write(chunk)
        if total == 0:
            raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")
        return temp_path, total
    except Exception:
        cleanup_files([temp_path])
        raise

def open_valid_pdf(path: str):
    try:
        doc = fitz.open(path)
        if doc.is_encrypted:
            doc.close()
            raise HTTPException(status_code=400, detail="Password-protected PDFs are not supported.")
        if len(doc) == 0:
            doc.close()
            raise HTTPException(status_code=400, detail="PDF has no pages.")
        if len(doc) > config.MAX_PDF_TOOL_PAGES:
            doc.close()
            raise HTTPException(
                status_code=413,
                detail=f"PDF has too many pages. Limit is {config.MAX_PDF_TOOL_PAGES} pages."
            )
        return doc
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF file structure.")

def safe_pdf_download_name(filename: str, suffix: str):
    base = os.path.splitext(os.path.basename(filename))[0].strip() or "document"
    return f"{base}_{suffix}.pdf"

def parse_page_selection(selection: str, page_count: int):
    pages = set()
    for part in selection.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            if not start_text.isdigit() or not end_text.isdigit():
                raise HTTPException(status_code=400, detail="Use page numbers like 1,3-5.")
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise HTTPException(status_code=400, detail="Page ranges must go from low to high.")
            pages.update(range(start, end + 1))
        else:
            if not part.isdigit():
                raise HTTPException(status_code=400, detail="Use page numbers like 1,3-5.")
            pages.add(int(part))
    if not pages:
        raise HTTPException(status_code=400, detail="Choose at least one page.")
    if min(pages) < 1 or max(pages) > page_count:
        raise HTTPException(status_code=400, detail=f"Pages must be between 1 and {page_count}.")
    return sorted(page - 1 for page in pages)

def parse_page_ranges(selection: str, page_count: int):
    ranges = []
    for part in selection.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
        else:
            start_text = end_text = part
        if not start_text.isdigit() or not end_text.isdigit():
            raise HTTPException(status_code=400, detail="Use ranges like 1-3,4-6.")
        start = int(start_text)
        end = int(end_text)
        if start > end:
            raise HTTPException(status_code=400, detail="Page ranges must go from low to high.")
        if start < 1 or end > page_count:
            raise HTTPException(status_code=400, detail=f"Ranges must be between 1 and {page_count}.")
        ranges.append((start - 1, end - 1))
    if not ranges:
        raise HTTPException(status_code=400, detail="Enter at least one page range.")
    return ranges

def parse_split_after(selection: str, page_count: int):
    points = []
    for part in selection.replace(" ", "").split(","):
        if not part:
            continue
        if not part.isdigit():
            raise HTTPException(status_code=400, detail="Use page numbers like 3,6,10.")
        point = int(part)
        if point < 1 or point >= page_count:
            raise HTTPException(status_code=400, detail=f"Split points must be between 1 and {page_count - 1}.")
        points.append(point)
    points = sorted(set(points))
    if not points:
        raise HTTPException(status_code=400, detail="Enter at least one split point.")

    ranges = []
    start = 0
    for point in points:
        ranges.append((start, point - 1))
        start = point
    ranges.append((start, page_count - 1))
    return ranges

def build_split_ranges(mode: str, instruction: str | None, page_count: int):
    if mode == "every_page":
        return [(page_index, page_index) for page_index in range(page_count)]
    if mode == "ranges":
        return parse_page_ranges(instruction or "", page_count)
    if mode == "after":
        return parse_split_after(instruction or "", page_count)
    raise HTTPException(status_code=400, detail="Choose a valid split mode.")

def create_zip_response(background_tasks: BackgroundTasks, files: list[tuple[str, str]], output_name: str):
    zip_path = os.path.join(tempfile.gettempdir(), f"pdf_pages_{os.urandom(8).hex()}.zip")
    import zipfile
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for source_path, archive_name in files:
            zip_file.write(source_path, archive_name)
    cleanup_targets = [zip_path] + [path for path, _ in files]
    background_tasks.add_task(cleanup_files, cleanup_targets)
    return FileResponse(path=zip_path, filename=output_name, media_type="application/zip")

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
                package = get_package(current_user["package_id"])
                period_start = parse_datetime(current_user["billing_period_starts_at"])
                period_end = parse_datetime(current_user["expires_at"])
                if not period_start or not period_end:
                    database.expire_subscription(current_user["id"])
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Monthly EFT subscription requires renewal before converting."
                    )

                usage = database.get_user_period_usage(current_user["id"], period_start, period_end)
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

@app.post("/api/pdf/preview")
async def preview_pdf(
    file: UploadFile = File(...),
    current_user = Depends(get_active_user)
):
    temp_pdf = None
    try:
        temp_pdf, file_size = save_upload_to_temp(file, "preview", get_pdf_tool_limit_bytes())
        doc = open_valid_pdf(temp_pdf)
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(0.55, 0.55), alpha=False)
        image_base64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
        metadata = {
            "filename": file.filename,
            "file_size": file_size,
            "page_count": len(doc),
            "first_page_width": round(page.rect.width),
            "first_page_height": round(page.rect.height),
            "preview_image": f"data:image/png;base64,{image_base64}",
        }
        doc.close()
        return metadata
    finally:
        cleanup_files([temp_pdf] if temp_pdf else [])

@app.post("/api/pdf/split")
async def split_pdf(
    background_tasks: BackgroundTasks,
    split_mode: str = Form("every_page"),
    split_pages: str = Form(""),
    file: UploadFile = File(...),
    current_user = Depends(get_active_user)
):
    temp_pdf = None
    output_files = []
    try:
        temp_pdf, _ = save_upload_to_temp(file, "split", get_pdf_tool_limit_bytes())
        doc = open_valid_pdf(temp_pdf)
        base_name = os.path.splitext(os.path.basename(file.filename))[0] or "document"
        split_ranges = build_split_ranges(split_mode, split_pages, len(doc))
        for segment_index, (start_page, end_page) in enumerate(split_ranges, start=1):
            out_doc = fitz.open()
            out_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)
            out_path = os.path.join(tempfile.gettempdir(), f"split_{os.urandom(8).hex()}.pdf")
            out_doc.save(out_path)
            out_doc.close()
            if start_page == end_page:
                archive_name = f"{base_name}_page_{start_page + 1}.pdf"
            else:
                archive_name = f"{base_name}_part_{segment_index}_pages_{start_page + 1}-{end_page + 1}.pdf"
            output_files.append((out_path, archive_name))
        doc.close()
        cleanup_files([temp_pdf])
        return create_zip_response(background_tasks, output_files, safe_pdf_download_name(file.filename, "split_pages").replace(".pdf", ".zip"))
    except Exception:
        cleanup_files([temp_pdf] + [path for path, _ in output_files if path])
        raise

@app.post("/api/pdf/extract")
async def extract_pdf_pages(
    background_tasks: BackgroundTasks,
    pages: str = Form(...),
    file: UploadFile = File(...),
    current_user = Depends(get_active_user)
):
    temp_pdf = None
    output_pdf = None
    try:
        temp_pdf, _ = save_upload_to_temp(file, "extract", get_pdf_tool_limit_bytes())
        doc = open_valid_pdf(temp_pdf)
        selected_pages = parse_page_selection(pages, len(doc))
        out_doc = fitz.open()
        for page_index in selected_pages:
            out_doc.insert_pdf(doc, from_page=page_index, to_page=page_index)
        output_pdf = os.path.join(tempfile.gettempdir(), f"extract_{os.urandom(8).hex()}.pdf")
        out_doc.save(output_pdf)
        out_doc.close()
        doc.close()
        cleanup_files([temp_pdf])
        background_tasks.add_task(cleanup_files, [output_pdf])
        return FileResponse(
            path=output_pdf,
            filename=safe_pdf_download_name(file.filename, "selected_pages"),
            media_type="application/pdf"
        )
    except Exception:
        cleanup_files([temp_pdf, output_pdf])
        raise

@app.post("/api/pdf/merge")
async def merge_pdfs(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    current_user = Depends(get_active_user)
):
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="Upload at least two PDFs to merge.")
    if len(files) > config.MAX_PDF_MERGE_FILES:
        raise HTTPException(status_code=413, detail=f"Merge is limited to {config.MAX_PDF_MERGE_FILES} PDFs.")

    temp_files = []
    output_pdf = None
    total_size = 0
    total_pages = 0
    merged = fitz.open()
    try:
        for file in files:
            remaining_bytes = get_pdf_merge_limit_bytes() - total_size
            if remaining_bytes <= 0:
                raise HTTPException(status_code=413, detail=f"Total merge size limit is {config.MAX_PDF_MERGE_TOTAL_MB}MB.")
            temp_pdf, file_size = save_upload_to_temp(file, "merge", remaining_bytes)
            temp_files.append(temp_pdf)
            total_size += file_size
            doc = open_valid_pdf(temp_pdf)
            total_pages += len(doc)
            if total_pages > config.MAX_PDF_TOOL_PAGES:
                doc.close()
                raise HTTPException(status_code=413, detail=f"Merged PDF is limited to {config.MAX_PDF_TOOL_PAGES} pages.")
            merged.insert_pdf(doc)
            doc.close()

        output_pdf = os.path.join(tempfile.gettempdir(), f"merged_{os.urandom(8).hex()}.pdf")
        merged.save(output_pdf)
        merged.close()
        cleanup_files(temp_files)
        background_tasks.add_task(cleanup_files, [output_pdf])
        return FileResponse(path=output_pdf, filename="merged_document.pdf", media_type="application/pdf")
    except Exception:
        merged.close()
        cleanup_files(temp_files + [output_pdf])
        raise

@app.get("/api/history")
def get_history(current_user = Depends(get_current_user)):
    return database.get_user_conversions(current_user["id"])

# --- ADMIN ENDPOINTS ---

@app.get("/api/admin/users")
def get_admin_users(current_user = Depends(get_current_user)):
    if current_user["profession"] != "Admin":
        raise HTTPException(status_code=403, detail="Admin permissions required.")
    return database.list_all_users()

@app.post("/api/admin/activate/{user_id}")
def activate_subscription(user_id: int, payload: ActivateSubscriptionSchema, current_user = Depends(get_current_user)):
    if current_user["profession"] != "Admin":
        raise HTTPException(status_code=403, detail="Admin permissions required.")

    package = get_package(payload.package_id)
    if package["id"] != payload.package_id:
        raise HTTPException(status_code=400, detail="Invalid package.")

    paid_until = parse_paid_until(payload.paid_until)
    if paid_until <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Paid-until date must be in the future.")

    success = database.activate_subscription(user_id, package["id"], paid_until)
    if not success:
        raise HTTPException(status_code=404, detail="User not found.")
    database.update_admin_note(user_id, payload.admin_note)

    return {
        "message": f"User activated on {package['name']} until {paid_until.date().isoformat()}."
    }

@app.post("/api/admin/status/{user_id}")
def update_status(user_id: int, status: str, current_user = Depends(get_current_user)):
    if current_user["profession"] != "Admin":
        raise HTTPException(status_code=403, detail="Admin permissions required.")
        
    if status not in ["pending", "active", "suspended"]:
        raise HTTPException(status_code=400, detail="Invalid status value.")

    if status == "active":
        raise HTTPException(status_code=400, detail="Use subscription activation to activate an EFT package.")
        
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
