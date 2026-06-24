# EducatorTools: PDF-to-Word SaaS Platform for Teachers

A mobile-first, flat, clean-style SaaS platform that allows teachers to log in, register, convert PDF test papers to Microsoft Word (`.docx`) documents with 100% layout and math symbol accuracy, and view their conversion history.

The application operates under a strict **Zero File Storage** privacy policy—documents are converted in temporary storage and deleted immediately after download.

---

## Technical Stack
*   **Frontend**: React (Vite) + Vanilla CSS (Light Mode, Flat design, Mobile-first responsive layout).
*   **Backend**: Python 3.11 (FastAPI).
*   **Conversion Engine**: `pdf2docx` (Sequential single-threaded mode to protect server CPU cores).
*   **Database**: SQLite (`backend/data/educator_tools.db`).
*   **Deployment**: Multi-stage Docker container (fits OCI Always Free ARM/x86 instances or Vercel/similar providers).

---

## Getting Started

### Local Development

#### 1. Setup Backend
Open your terminal inside the `backend` directory:
```bash
# Navigate to backend
cd backend

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
uvicorn main:app --reload --port 8000
```
The backend will run on `http://localhost:8000`. On first run, it automatically initializes the SQLite database and sets up the default admin.

#### 2. Setup Frontend
Open another terminal inside the `frontend` directory:
```bash
# Navigate to frontend
cd frontend

# Install node dependencies
npm install

# Start Vite dev server
npm run dev
```
The React frontend will start on `http://localhost:5173`. Any API calls are routed through the backend proxy.

---

## Docker Deployment (Oracle Cloud / OCI)

The entire stack is containerized, serving both frontend assets and the backend API on port `8000`.

### 1. Build Docker Image
Run from the root of the repository:
```bash
docker build -t educator-tools .
```

### 2. Run Container with Resource Restrictions
To ensure that PDF conversions do not cause resource spikes or interfere with other applications running on your OCI cloud server, run the container with hard CPU and memory limits:
```bash
docker run -d \
  -p 8000:8000 \
  --cpus="1.5" \
  --memory="2g" \
  --name educator-tools-instance \
  -v educator_db_data:/app/backend/data \
  --restart unless-stopped \
  educator-tools
```
*   `--cpus="1.5"`: Limits the container to a maximum of 1.5 CPU cores.
*   `--memory="2g"`: Limits the container to a maximum of 2GB RAM.
*   `-v educator_db_data:/app/backend/data`: Mounts a persistent volume for the SQLite database so user accounts and histories are preserved across container updates/reloads.

---

## Administrator Dashboard
To activate teachers after validating their manual EFT payments:
1. Log in with the default admin account:
   * **Email**: `admin@educatortools.co.za`
   * **Password**: `AdminPassword123!`
2. You will be redirected to the Admin panel to search for teachers, see their profession details, and click **"Approve EFT (Activate)"** to unlock their PDF converter dashboard.
3. *Recommendation:* Log in and immediately change your administrator password or create a custom admin entry.
