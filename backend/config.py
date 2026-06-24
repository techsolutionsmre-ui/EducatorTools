import os

# JWT Authentication Config
JWT_SECRET = "educator_tools_flat_mode_secret_key_18223!"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 Days token lifespan

# Support and Billing Info
CONTACT_EMAIL = "support@educatortools.co.za"

# Database Configuration (SQLite)
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "educator_tools.db")

# Concurrency Controls (Strictly limit resources to prevent CPU spikes)
MAX_CONCURRENT_CONVERSIONS = 1  # Process one PDF at a time
MAX_CPU_THREADS = 1             # Limit pdf2docx to a single thread/core

# Ensure database directory exists
os.makedirs(DB_DIR, exist_ok=True)
