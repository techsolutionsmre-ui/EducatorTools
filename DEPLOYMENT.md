# EducatorTools: Deployment Guide (Vercel & Oracle Cloud Infrastructure)

This guide walks you through the step-by-step process of deploying the **EducatorTools** SaaS platform. The frontend is hosted on **Vercel** for optimal load times, while the backend API and SQLite database run inside a resource-constrained **Docker** container on **Oracle Cloud Infrastructure (OCI)**.

---

## Part 1: Git and Code Preparation

Before deploying, ensure your local changes are committed and pushed to your remote GitHub repository.

### Command Execution:
Run these commands from your local machine inside the project root directory (`C:\Users\Masondo\Downloads\EducatorTools`):

```bash
# 1. Stage all changes to Git's index
git add .

# 2. Record the staged changes to the repository history
git commit -m "feat: Add flat UI theme and dual-engine PDF converter"

# 3. Upload your local commits to the remote GitHub repository
git push origin main
```

#### Code Explanation for Junior Developers:
*   `git add .`: Staged files tell Git which modifications you want to save. The `.` specifies that all files in the current folder (recursively) should be added.
*   `git commit -m "..."`: Saves the staged files as a permanent snapshot in your local history. The `-m` flag specifies a short message describing the changes.
*   `git push origin main`: Uploads the local commits to the remote server (`origin`) on the main branch (`main`), making the code available for OCI and Vercel.

---

## Part 2: Backend Deployment on Oracle Cloud Infrastructure (OCI)

To host the API, database, and conversion server, you must connect to your remote OCI instance, pull the repository, and run it inside a Docker container.

### Step 1: Connect to your OCI Server via SSH
Open a terminal on your computer and log in to your OCI server:
```bash
ssh -i /path/to/your/private_key.key ubuntu@YOUR_OCI_PUBLIC_IP
```
*   `ssh`: The Secure Shell command used to log in to remote servers.
*   `-i /path/to/key.key`: Points to the private SSH key file required to authenticate.
*   `ubuntu@...`: Logging in as the `ubuntu` user (standard default for OCI Linux instances) to your OCI server's public IP address.

### Step 2: Clone or Pull the Code on OCI
Once logged into your OCI command line:

#### If this is the first time setting up the project on the server:
```bash
# Clone the repository using SSH
git clone git@github.com:techsolutionsmre-ui/EducatorTools.git
```
*   `git clone`: Downloads a copy of the target repository onto the server.

#### If you are updating an existing setup on the server:
```bash
# Navigate to the project root folder
cd EducatorTools

# Pull the latest changes from GitHub
git pull origin main
```
*   `cd`: "Change directory" to move into the project folder.
*   `git pull`: Downloads the latest commits from the GitHub repository and merges them into your active files.

### Step 3: Build the Docker Image
```bash
docker build -t educator-tools .
```
*   `docker build`: Creates a read-only blueprint (an "image") of your application based on the instructions inside the `Dockerfile`.
*   `-t educator-tools`: Tags (names) the image `educator-tools` so you can reference it easily.
*   `.`: Tells Docker to find the `Dockerfile` and all context files in the current folder.

### Step 4: Run the Docker Container with Resource Caps
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

#### Detailed Flag Breakdown for Junior Developers:
*   `docker run`: Instantiates and starts a runnable container from a specified image.
*   `-d` (Detached Mode): Runs the container in the background. It allows you to close your terminal session without stopping the application.
*   `-p 8000:8000` (Port Mapping): Binds port `8000` of the host OCI server to port `8000` inside the container. Traffic hitting `http://<your-oci-ip>:8000` will be routed into your FastAPI app.
*   `--cpus="1.5"` (CPU Hard Cap): Restricts the container to using a maximum of 1.5 CPU cores. This prevents PDF parsing from hogging 100% of your OCI CPUs and stalling other websites or apps on the server.
*   `--memory="2g"` (RAM Limit): Limits the memory allocation to 2 Gigabytes.
*   `--name educator-tools-instance`: Sets a friendly name to identify this specific running container instance (used for logs and commands).
*   `-v educator_db_data:/app/backend/data` (Volume Mount): Mounts a persistent virtual disk volume to the SQLite database storage path. This ensures that user accounts, passwords, and histories **never get wiped** when you rebuild or stop the container.
*   `--restart unless-stopped` (Auto-Restart): Tells Docker to automatically reboot the container if it crashes or if the OCI server restarts.
*   `educator-tools`: The name of the Docker image to build the container from.

#### Maintenance Commands:
```bash
# View active container logs (live stream)
docker logs -f educator-tools-instance

# Stop the running container
docker stop educator-tools-instance

# Delete the container instance (does not delete your database volume!)
docker rm educator-tools-instance
```

---

## Part 3: Frontend Deployment on Vercel

Vercel hosts the client React code. We configure a rewrite rule so that API requests go directly to your OCI server.

### Step 1: Configure the API Rewrite Rule
1. Open the [frontend/vercel.json](file:///C:/Users/Masondo/Downloads/EducatorTools/frontend/vercel.json) file on your computer.
2. Replace `CHANGE_TO_YOUR_OCI_IP_OR_DOMAIN` with the public IP address of your OCI server (or domain name, if you mapped one).
3. Commit and push the changes:
   ```json
   {
     "rewrites": [
       {
         "source": "/api/:path*",
         "destination": "http://129.151.XX.XX:8000/api/:path*"
       }
     ]
   }
   ```
*Why this is important:* In production, Vercel serves files via HTTPS. The browser would block raw calls to another IP due to CORS restrictions. The Vercel `rewrites` configuration acts as a proxy, receiving requests on `/api` and forwarding them securely to OCI.

### Step 2: Deploy on Vercel Dashboard
1. Go to [Vercel](https://vercel.com/) and log in.
2. Click **Add New Project** and select your `EducatorTools` GitHub repository.
3. Under **Project Settings**:
   *   **Root Directory**: Click "Edit" and choose the **`frontend`** directory. (Vercel will build Vite/React in isolation).
   *   **Framework Preset**: Leave it as `Vite` (automatically detected).
4. Click **Deploy**. Vercel will compile the React code and output a public domain (e.g. `educator-tools.vercel.app`).
