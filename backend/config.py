import os

# JWT Authentication Config
JWT_SECRET = os.getenv("JWT_SECRET", "educator_tools_flat_mode_secret_key_18223!")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 Days token lifespan

# Support and Billing Info
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", os.getenv("ADMIN_EMAIL", "techsolutions.mre@gmail.com"))
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "techsolutions.mre@gmail.com").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeThisAdminPassword123!")
FRONTEND_APP_URL = os.getenv("FRONTEND_APP_URL", "https://educatortools.pages.dev").rstrip("/")
SUBSCRIPTION_PRICE_ZAR = int(os.getenv("SUBSCRIPTION_PRICE_ZAR", "29"))
DEFAULT_PACKAGE_ID = os.getenv("DEFAULT_PACKAGE_ID", "starter")
PACKAGES = [
    {
        "id": "starter",
        "name": "Conversion Starter",
        "price_zar": 29,
        "billing_period": "monthly",
        "monthly_pages": 29,
    },
    {
        "id": "teacher-plus",
        "name": "Conversion Plus",
        "price_zar": 49,
        "billing_period": "monthly",
        "monthly_pages": 100,
    },
]

BANK_NAME = "Capitec Business"
BANK_ACCOUNT_NUMBER = "1052 9674 00"
BANK_BRANCH_CODE = "450105"
BANK_ACCOUNT_TYPE = "Current/Cheque"

# Email Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_SECURE = os.getenv("SMTP_SECURE", "false").strip().lower() == "true"
SMTP_USER = os.getenv("SMTP_USER", os.getenv("EMAIL_USER", ""))
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", os.getenv("SMTP_PASS", os.getenv("EMAIL_PASSWORD", "")))
SMTP_FROM = os.getenv("SMTP_FROM", os.getenv("EMAIL_FROM", "Educator Tools <techsolutions.mre@gmail.com>"))

# Database Configuration (SQLite)
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "educator_tools.db")

# Concurrency Controls (Strictly limit resources to prevent CPU spikes)
MAX_CONCURRENT_CONVERSIONS = int(os.getenv("MAX_CONCURRENT_CONVERSIONS", "1"))  # Process one PDF at a time
MAX_CPU_THREADS = int(os.getenv("MAX_CPU_THREADS", "1"))             # Limit pdf2docx to a single thread/core

# Lightweight PDF tools limits
MAX_PDF_TOOL_FILE_MB = int(os.getenv("MAX_PDF_TOOL_FILE_MB", "25"))
MAX_PDF_MERGE_TOTAL_MB = int(os.getenv("MAX_PDF_MERGE_TOTAL_MB", "50"))
MAX_PDF_MERGE_FILES = int(os.getenv("MAX_PDF_MERGE_FILES", "5"))
MAX_PDF_TOOL_PAGES = int(os.getenv("MAX_PDF_TOOL_PAGES", "80"))

# Ensure database directory exists
os.makedirs(DB_DIR, exist_ok=True)
