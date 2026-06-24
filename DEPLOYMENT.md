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

## Part 3: Frontend Deployment on Cloudflare Pages

Cloudflare Pages hosts the client React code. We configure a Pages Function to act as a reverse proxy so that API requests go directly to your OCI server.

### Step 1: Configure the API Proxy Target
Instead of hardcoding your OCI server IP in configuration files, we use a Cloudflare Environment Variable. This keeps your configuration clean and dynamic.

1. Commit and push the frontend changes (including the `frontend/functions/api/[[path]].js` file and the `frontend/public/_redirects` file).
2. Go to the [Cloudflare Dashboard](https://dash.cloudflare.com/) and navigate to **Workers & Pages**.
3. Create a new Pages project connected to your GitHub repository.

### Step 2: Configure Cloudflare Pages Build & Environment
In the Cloudflare Pages build settings screen (as shown in your screenshot):

1. **Framework Preset**: Select `React (Vite)`.
2. **Build Command**: Set to `npm run build`.
3. **Build Output Directory**: Set to `dist`.
4. **Root Directory (Advanced)**: 
   * Expand this section.
   * Set the root directory to **`frontend`**. This is critical because the React application lives in the `/frontend` subfolder.
5. **Environment Variables (Advanced)**:
   * Expand this section.
   * Add a new environment variable:
     * **Variable Name**: `BACKEND_API_URL`
     * **Value**: `http://YOUR_OCI_PUBLIC_IP:8000` (Replace with your actual OCI server IP address, keeping the `:8000` port prefix).
6. Click **Save and Deploy**. Cloudflare Pages will build the React code and set up the edge proxy function automatically, serving your application on a custom `*.pages.dev` subdomain with HTTPS enabled.

