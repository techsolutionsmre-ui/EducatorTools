export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  
  // Get the backend API base URL from environment variables, or fallback to the OCI IP placeholder
  const backendBaseUrl = env.BACKEND_API_URL || 'http://CHANGE_TO_YOUR_OCI_IP_OR_DOMAIN:8000';
  
  // Construct the target URL (e.g. /api/auth/login -> http://YOUR_OCI_IP:8000/api/auth/login)
  const targetUrl = `${backendBaseUrl}${url.pathname}${url.search}`;

  try {
    // Clone headers to avoid mutation issues
    const headers = new Headers(request.headers);
    
    // Check if the request has a body
    const hasBody = !['GET', 'HEAD'].includes(request.method);
    const fetchOptions = {
      method: request.method,
      headers: headers,
      redirect: 'manual',
    };
    
    if (hasBody) {
      fetchOptions.body = request.body;
    }

    const response = await fetch(targetUrl, fetchOptions);
    return response;
  } catch (error) {
    return new Response(JSON.stringify({ 
      error: 'Failed to proxy request to backend', 
      details: error.message,
      targetUrl: targetUrl 
    }), {
      status: 502,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
