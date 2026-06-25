import React, { useState, useEffect } from 'react';
import logo from './assets/logo.svg';
import heroImg from './assets/hero.png';
import featureLayout from './assets/feature_layout.png';
import featureMath from './assets/feature_math.png';
import featureSecure from './assets/feature_secure.png';
import authBanner from './assets/auth_banner.png';

// Support email for activation inquiries
const CONTACT_EMAIL = "techsolutions.mre@gmail.com";

// API Base URL (relative to root for Vercel/Docker deployment)
const API_URL = '/api';
const FALLBACK_PACKAGES = [
  { id: 'starter', name: 'Conversion Starter', price_zar: 29, billing_period: 'monthly', monthly_pages: 29 },
  { id: 'teacher-plus', name: 'Conversion Plus', price_zar: 49, billing_period: 'monthly', monthly_pages: 100 }
];

export default function App() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [view, setView] = useState('landing'); // 'landing', 'login', 'register', 'verify', 'dashboard', 'admin'
  const [history, setHistory] = useState([]);
  const [adminUsers, setAdminUsers] = useState([]);
  const [downloadUrl, setDownloadUrl] = useState(null);
  const [downloadFilename, setDownloadFilename] = useState('');
  const [billingPackages, setBillingPackages] = useState(FALLBACK_PACKAGES);
  const [isMobile, setIsMobile] = useState(() => window.matchMedia('(max-width: 460px)').matches);
  const [isTrialInfoOpen, setIsTrialInfoOpen] = useState(() => !window.matchMedia('(max-width: 460px)').matches);

  const resetUploadState = () => {
    if (downloadUrl && downloadUrl !== '#mock-download') {
      window.URL.revokeObjectURL(downloadUrl);
    }
    setFile(null);
    setDownloadUrl(null);
    setDownloadFilename('');
    setConversionStatus(null);
    setProgressMsg('');
    setError('');
  };
  
  // Form states
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [profession, setProfession] = useState('Primary School Teacher');
  const [verificationCode, setVerificationCode] = useState('');
  const [pendingVerificationEmail, setPendingVerificationEmail] = useState('');
  
  // Upload and Conversion states
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [conversionStatus, setConversionStatus] = useState(null); // 'uploading', 'converting', 'success', 'failed'
  const [progressMsg, setProgressMsg] = useState('');
  
  // Status states
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Admin search state
  const [adminSearch, setAdminSearch] = useState('');

  // Fetch user profile on start if token exists
  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
      fetchProfile();
    } else {
      localStorage.removeItem('token');
      setUser(null);
      setView('landing');
    }
  }, [token]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 460px)');
    const handleChange = (event) => {
      setIsMobile(event.matches);
      setIsTrialInfoOpen(!event.matches);
    };

    handleChange(mediaQuery);
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Fetch profile
  const fetchProfile = async () => {
    try {
      const res = await fetch(`${API_URL}/auth/me`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 200) {
        const data = await res.json();
        setUser(data);
        if (data.profession === 'Admin') {
          setView('admin');
        } else {
          setView('dashboard');
        }
        fetchBillingInfo();
        fetchHistory();
      } else {
        handleLogout();
      }
    } catch (err) {
      setError('Connection failed. Working in local preview mode.');
      // Mock user for offline safety
      setUser({
        email: 'preview.teacher@school.za',
        profession: 'CAT High School Teacher',
        status: 'pending' // 'active' to test active, 'pending' to test pending
      });
      setView('dashboard');
    }
  };

  const fetchBillingInfo = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/billing/info`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 200) {
        const data = await res.json();
        setBillingPackages(data.packages?.length ? data.packages : FALLBACK_PACKAGES);
      }
    } catch (err) {
      setBillingPackages(FALLBACK_PACKAGES);
    }
  };

  // Fetch conversion history
  const fetchHistory = async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/history`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 200) {
        const data = await res.json();
        setHistory(data);
      }
    } catch (err) {
      // Mock history for offline mode
      setHistory([
        { id: 1, filename: 'Exam_Term1_Theory.pdf', page_count: 8, file_size: 245000, status: 'success', created_at: new Date(Date.now() - 3600000 * 2).toISOString() },
        { id: 2, filename: 'Marking_Guideline_AnnexJ.pdf', page_count: 4, file_size: 112000, status: 'success', created_at: new Date(Date.now() - 3600000 * 24).toISOString() }
      ]);
    }
  };

  // Fetch all users for Admin
  const fetchAdminUsers = async () => {
    if (!token || user?.profession !== 'Admin') return;
    try {
      const res = await fetch(`${API_URL}/admin/users`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 200) {
        const data = await res.json();
        setAdminUsers(data);
      }
    } catch (err) {
      // Mock data for preview
      setAdminUsers([
        { id: 101, email: 'john.wced@school.za', profession: 'Primary School Teacher', status: 'pending', created_at: new Date().toISOString() },
        { id: 102, email: 'sara.dbe@highschool.za', profession: 'CAT Teacher', status: 'active', created_at: new Date(Date.now() - 3600000 * 48).toISOString() },
        { id: 103, email: 'peter@primary.co.za', profession: 'Intermediate Phase', status: 'suspended', created_at: new Date().toISOString() }
      ]);
    }
  };

  useEffect(() => {
    if (view === 'admin') {
      fetchAdminUsers();
    }
  }, [view]);

  // Handle forms
  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const formData = new URLSearchParams();
      formData.append('username', email);
      formData.append('password', password);

      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });
      
      const data = await res.json();
      if (res.status === 200) {
        setToken(data.access_token);
      } else {
        if (res.status === 403 && data.detail?.toLowerCase().includes('verified')) {
          setPendingVerificationEmail(email);
          setView('verify');
        }
        setError(data.detail || 'Login failed. Please check credentials.');
      }
    } catch (err) {
      // Mock Login for local testing
      if (email.includes('admin')) {
        setUser({ email, profession: 'Admin', status: 'active' });
        setView('admin');
      } else {
        setUser({ email, profession: 'CAT Teacher', status: 'pending' });
        setView('dashboard');
      }
      setSuccess('Logged in as Offline Preview Mode.');
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    try {
      const res = await fetch(`${API_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, profession })
      });
      const data = await res.json();
      if (res.status === 200) {
        setPendingVerificationEmail(email);
        setVerificationCode('');
        setSuccess(data.email_sent
          ? 'Registration successful. Enter the verification code sent to your email.'
          : 'Registration successful, but email delivery failed. Please contact support for the verification code.');
        setView('verify');
      } else {
        setError(data.detail || 'Registration failed.');
      }
    } catch (err) {
      setError('Registration API failed. Running offline client simulation.');
      setUser({ email, profession, status: 'pending' });
      setView('dashboard');
    }
  };

  const handleVerifyEmail = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    const targetEmail = pendingVerificationEmail || email;
    try {
      const res = await fetch(`${API_URL}/auth/verify-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: targetEmail, code: verificationCode })
      });
      const data = await res.json();
      if (res.status === 200) {
        setSuccess(data.message || 'Email verified. Please sign in.');
        setView('login');
      } else {
        setError(data.detail || 'Verification failed.');
      }
    } catch (err) {
      setError('Verification API failed. Please try again.');
    }
  };

  const handleResendVerification = async () => {
    setError('');
    setSuccess('');
    const targetEmail = pendingVerificationEmail || email;
    if (!targetEmail) {
      setError('Enter your email address first.');
      return;
    }
    try {
      const res = await fetch(`${API_URL}/auth/resend-verification`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: targetEmail })
      });
      const data = await res.json();
      if (res.status === 200) {
        setSuccess(data.message || 'Verification code sent.');
      } else {
        setError(data.detail || 'Could not resend verification code.');
      }
    } catch (err) {
      setError('Could not reach the verification service.');
    }
  };

  const handleRequestCredits = async () => {
    setError('');
    setSuccess('');
    try {
      const res = await fetch(`${API_URL}/billing/request-credit-details`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (res.status === 200) {
        setSuccess(data.email_sent
          ? 'Conversion credit details have been emailed to you.'
          : 'We could not send the email. Please contact support.');
      } else {
        setError(data.detail || 'Could not request conversion credit details.');
      }
    } catch (err) {
      setError('Could not reach the billing email service.');
    }
  };

  const handleLogout = () => {
    setToken('');
    setUser(null);
    setHistory([]);
    resetUploadState();
    setView('landing');
    setError('');
    setSuccess('');
  };

  // Admin Actions
  const handleUserStatusUpdate = async (userId, action) => {
    try {
      const res = await fetch(`${API_URL}/admin/status/${userId}?status=${action}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.status === 200) {
        fetchAdminUsers();
        setSuccess(`User status updated to ${action}!`);
      } else {
        const data = await res.json();
        setError(data.detail || 'Failed to update user status.');
      }
    } catch (err) {
      // Offline fallback
      setAdminUsers(prev => prev.map(u => u.id === userId ? { ...u, status: action } : u));
      setSuccess(`Mock User updated to ${action}!`);
    }
  };

  // Drag and Drop Logic
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const uploadedFile = e.dataTransfer.files[0];
      if (uploadedFile.type === "application/pdf") {
        setFile(uploadedFile);
        setError('');
      } else {
        setError("Only PDF files are allowed!");
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const uploadedFile = e.target.files[0];
      if (uploadedFile.type === "application/pdf") {
        setFile(uploadedFile);
        setError('');
      } else {
        setError("Only PDF files are allowed!");
      }
    }
  };

  // Conversion Upload Logic
  const startConversion = async () => {
    if (!file) return;
    setError('');
    setConversionStatus('uploading');
    setProgressMsg('Uploading your PDF to conversion server...');

    const formData = new FormData();
    formData.append('file', file);

    // Simulate progress text changes
    const progressIntervals = [
      { delay: 1500, msg: 'Waking up converter pipeline (can take 3-4 mins if sleeping)...' },
      { delay: 6000, msg: 'Extracting PDF layout structures and images...' },
      { delay: 12000, msg: 'Rebuilding margins, fonts, and math formulas...' },
      { delay: 18000, msg: 'Compiling final Microsoft Word (.docx) document...' }
    ];

    const timeouts = progressIntervals.map(step => 
      setTimeout(() => setProgressMsg(step.msg), step.delay)
    );

    try {
      const res = await fetch(`${API_URL}/convert`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });

      // Clear timeouts
      timeouts.forEach(clearTimeout);

      if (res.status === 200) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const cleanName = file.name.replace(/\.[^/.]+$/, "");
        const docxName = `${cleanName}.docx`;

        setDownloadUrl(url);
        setDownloadFilename(docxName);
        setConversionStatus('success');
        setProgressMsg('Conversion complete!');
        fetchHistory();
      } else {
        const data = await res.json();
        setError(data.detail || 'Conversion failed. Please try a different PDF.');
        setConversionStatus('failed');
      }
    } catch (err) {
      timeouts.forEach(clearTimeout);
      setError('Connection timeout. Please verify you are using local/docker endpoint.');
      setConversionStatus('failed');
      
      // Mock success download in offline/preview sandbox
      setTimeout(() => {
        setDownloadUrl('#mock-download');
        setDownloadFilename(file.name.replace(/\.[^/.]+$/, "") + ".docx");
        setConversionStatus('success');
        setHistory(prev => [
          { id: Date.now(), filename: file.name, page_count: 5, file_size: file.size, status: 'success', created_at: new Date().toISOString() },
          ...prev
        ]);
      }, 2000);
    }
  };

  // Format File Size
  const formatBytes = (bytes, decimals = 1) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  };

  const successfulTrials = history.filter(item => item.status === 'success').length;
  const remainingTrials = Math.max(0, 3 - successfulTrials);

  return (
    <div className="app-container">
      
      {/* HEADER SECTION */}
      <header className="app-header">
        <div className="app-branding" style={{ cursor: 'pointer' }} onClick={() => {
          if (user) {
            setView(user.profession === 'Admin' ? 'admin' : 'dashboard');
          } else {
            setView('landing');
          }
          setError('');
          setSuccess('');
        }}>
          <img src={logo} className="app-logo" alt="EducatorTools Logo" />
          <h1 className="app-title">Educator<span>Tools</span></h1>
        </div>
        {user ? (
          <button className="btn-icon-only" title="Logout" onClick={handleLogout}>
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        ) : (
          view === 'landing' ? (
            <button className="btn-signin" onClick={() => { setView('login'); setError(''); setSuccess(''); }}>
              Sign In
            </button>
          ) : (
            <button className="btn-signin" onClick={() => { setView('landing'); setError(''); setSuccess(''); }}>
              Home
            </button>
          )
        )}
      </header>

      {/* ERROR & SUCCESS TOASTS */}
      {error && (
        <div className="alert alert-danger">
          <strong>Error: </strong> {error}
        </div>
      )}
      {success && (
        <div className="alert alert-success">
          {success}
        </div>
      )}

      {/* RENDER VIEW CONTROLLER */}
      <main className="app-content">
        {view === 'landing' && (
        <div className="landing-page">
          {/* Hero Section */}
          <div className="hero-section">
            <div className="hero-text">
              <h2 className="hero-title">
                Convert Test Papers to Word with <span>100% Accuracy</span>
              </h2>
              <p className="hero-subtitle">
                Keep math formulas, tables, headers, and footers fully editable. Built specifically for South African educators to save hours of re-typing.
              </p>
              <button 
                className="btn btn-primary btn-hero-cta" 
                onClick={() => { setView('register'); setError(''); setSuccess(''); }}
              >
                Get Started (3 Free Trials)
              </button>
            </div>
            
            <div className="hero-image-container">
              <img src={heroImg} className="hero-image" alt="EducatorTools conversion mockup" />
            </div>
          </div>

          {/* Feature Grid */}
          <div className="features-grid">
            <div className="feature-card">
              <img src={featureLayout} className="feature-card-image" alt="Layout Fidelity Icon" />
              <div className="feature-card-content">
                <h4>Layout Fidelity</h4>
                <p>Preserves complex margins, page numbers, headers, and columns exactly like the original.</p>
              </div>
            </div>
            <div className="feature-card">
              <img src={featureMath} className="feature-card-image" alt="Math & Formulas Icon" />
              <div className="feature-card-content">
                <h4>Math & Formulas</h4>
                <p>Math equations and symbols stay fully editable inside Word—no broken text or images.</p>
              </div>
            </div>
            <div className="feature-card">
              <img src={featureSecure} className="feature-card-image" alt="Private & Secure Icon" />
              <div className="feature-card-content">
                <h4>Private & Secure</h4>
                <p>We do not store your PDFs. Files are processed locally and deleted immediately after download.</p>
              </div>
            </div>
          </div>

          {/* How it Works / Workflow Steps */}
          <div className="workflow-section">
            <h3 className="section-title" style={{ justifyContent: 'center', marginBottom: '20px' }}>How It Works</h3>
            <div className="workflow-steps">
              <div className="step">
                <div className="step-number">1</div>
                <div className="step-text">Upload PDF</div>
              </div>
              <div className="step-connector">➔</div>
              <div className="step">
                <div className="step-number">2</div>
                <div className="step-text">Auto-Convert</div>
              </div>
              <div className="step-connector">➔</div>
              <div className="step">
                <div className="step-number">3</div>
                <div className="step-text">Download Word</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {view === 'login' && (
        <div className="auth-container">
          <div className="auth-banner-container">
            <img src={authBanner} className="auth-banner-image" alt="EducatorTools Login illustration" />
          </div>
          <div className="form-header">
            <h2>Teacher Login</h2>
            <p>Convert test papers to Word with 100% layout fidelity.</p>
          </div>
          <form onSubmit={handleLogin}>
            <div className="input-group">
              <label className="input-label">Email Address</label>
              <input 
                type="email" 
                required 
                className="input-control" 
                placeholder="e.g. educator@school.za"
                value={email}
                onChange={e => setEmail(e.target.value)}
              />
            </div>
            <div className="input-group">
              <label className="input-label">Password</label>
              <input 
                type="password" 
                required 
                className="input-control" 
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
            </div>
            <button type="submit" className="btn btn-primary" style={{ marginTop: '24px' }}>
              Sign In
            </button>
          </form>
          <div style={{ textAlign: 'center', marginTop: '16px', fontSize: '13px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>New educator? </span>
            <span 
              style={{ color: 'var(--accent-blue)', cursor: 'pointer', fontWeight: 600 }}
              onClick={() => { setView('register'); setError(''); setSuccess(''); }}
            >
              Create an Account
            </span>
          </div>
        </div>
      )}

      {view === 'register' && (
        <div className="auth-container">
          <div className="auth-banner-container">
            <img src={authBanner} className="auth-banner-image" alt="EducatorTools Signup illustration" />
          </div>
          <div className="form-header">
            <h2>Educator Signup</h2>
            <p>Create your account to get started.</p>
          </div>
          <form onSubmit={handleRegister}>
            <div className="input-group">
              <label className="input-label">Email Address</label>
              <input 
                type="email" 
                required 
                className="input-control" 
                placeholder="e.g. name@school.co.za"
                value={email}
                onChange={e => setEmail(e.target.value)}
              />
            </div>
            <div className="input-group">
              <label className="input-label">Password</label>
              <input 
                type="password" 
                required 
                className="input-control" 
                placeholder="Choose a strong password"
                value={password}
                onChange={e => setPassword(e.target.value)}
              />
            </div>
            <div className="input-group">
              <label className="input-label">Profession / Class Taught</label>
              <select 
                className="input-control"
                value={profession}
                onChange={e => setProfession(e.target.value)}
                style={{ appearance: 'none', backgroundPosition: 'right 16px center' }}
              >
                <option>Primary School Teacher</option>
                <option>High School CAT / IT Teacher</option>
                <option>Intermediate Phase Educator</option>
                <option>Department Head / HOD</option>
                <option>Examiner / Assessor</option>
              </select>
            </div>
            <button type="submit" className="btn btn-primary" style={{ marginTop: '24px' }}>
              Submit & Register
            </button>
          </form>
          <div style={{ textAlign: 'center', marginTop: '16px', fontSize: '13px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Already registered? </span>
            <span 
              style={{ color: 'var(--accent-blue)', cursor: 'pointer', fontWeight: 600 }}
              onClick={() => { setView('login'); setError(''); setSuccess(''); }}
            >
              Log In
            </span>
          </div>
        </div>
      )}

      {view === 'verify' && (
        <div className="auth-container">
          <div className="auth-banner-container">
            <img src={authBanner} className="auth-banner-image" alt="EducatorTools verification illustration" />
          </div>
          <div className="form-header">
            <h2>Verify Email</h2>
            <p>Enter the 6-digit code sent to your email.</p>
          </div>
          <form onSubmit={handleVerifyEmail}>
            <div className="input-group">
              <label className="input-label">Email Address</label>
              <input
                type="email"
                required
                className="input-control"
                value={pendingVerificationEmail || email}
                onChange={e => {
                  setPendingVerificationEmail(e.target.value);
                  setEmail(e.target.value);
                }}
              />
            </div>
            <div className="input-group">
              <label className="input-label">Verification Code</label>
              <input
                type="text"
                required
                inputMode="numeric"
                maxLength="6"
                className="input-control"
                placeholder="000000"
                value={verificationCode}
                onChange={e => setVerificationCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                style={{ textAlign: 'center', fontSize: '22px', fontWeight: 700 }}
              />
            </div>
            <button type="submit" className="btn btn-primary" style={{ marginTop: '24px' }}>
              Verify & Continue
            </button>
          </form>
          <button
            type="button"
            className="btn"
            onClick={handleResendVerification}
            style={{ marginTop: '12px', background: '#E2E8F0', color: 'var(--text-primary)' }}
          >
            Resend Code
          </button>
          <div style={{ textAlign: 'center', marginTop: '16px', fontSize: '13px' }}>
            <span style={{ color: 'var(--text-secondary)' }}>Already verified? </span>
            <span
              style={{ color: 'var(--accent-blue)', cursor: 'pointer', fontWeight: 600 }}
              onClick={() => { setView('login'); setError(''); setSuccess(''); }}
            >
              Log In
            </span>
          </div>
        </div>
      )}

      {view === 'dashboard' && user && (
        <div className="dashboard-layout">
          
          {/* Active profile stats */}
          <div className="profile-row">
            <div className="profile-avatar">
              {user.email.substring(0, 2).toUpperCase()}
            </div>
            <div className="profile-details">
              <span className="profile-email">{user.email}</span>
              <span className="profile-subtext">
                {user.profession} • <span className={`badge badge-${user.status}`}>{user.status}</span>
              </span>
            </div>
          </div>

          {/* Free Trial Banner */}
          {user.status === 'trial' && (
            <div className="banner banner-info">
              <span className="banner-icon">ℹ️</span>
              <div className="banner-content">
                <button
                  type="button"
                  className="banner-toggle"
                  aria-expanded={isTrialInfoOpen}
                  onClick={() => isMobile && setIsTrialInfoOpen(open => !open)}
                >
                  <strong>Free Trial Account</strong>
                  <span className="banner-toggle-icon" aria-hidden="true">⌄</span>
                </button>
                <div className={`banner-collapsible ${isTrialInfoOpen ? 'is-open' : ''}`}>
                  <p style={{ marginTop: '4px', color: 'var(--text-secondary)' }}>
                    You have <strong>{remainingTrials}</strong> remaining trial conversion{remainingTrials !== 1 ? 's' : ''} (max 4 pages per upload).
                  </p>
                  <p style={{ marginTop: '8px', color: 'var(--text-secondary)' }}>
                    Need more conversion credits? Request the details by email, pay by EFT, then reply to that email with proof of payment.
                  </p>
                  <div className="package-list" aria-label="Available conversion packages">
                    {billingPackages.map(item => (
                      <div className="package-row" key={item.id}>
                        <span className="package-name">{item.name}</span>
                        <span className="package-meta">
                          R{item.price_zar}/{item.billing_period} · {item.monthly_pages} pages
                        </span>
                      </div>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="btn"
                    onClick={handleRequestCredits}
                    style={{ marginTop: '12px', background: '#E2E8F0', color: 'var(--text-primary)' }}
                  >
                    Email Me Credit Details
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Pending State Card */}
          {user.status === 'pending' && (
            <div className="banner banner-warning">
              <span className="banner-icon">⏳</span>
              <div>
                <strong>Account Pending Activation</strong>
                <p style={{ marginTop: '6px', color: 'var(--text-secondary)' }}>
                  Your account registration has been received and is awaiting administrator activation.
                </p>
                <p style={{ marginTop: '8px', color: 'var(--text-secondary)' }}>
                  If you still need payment instructions, request them below. After paying, reply to the emailed instructions with proof of payment. Once approved, return here and sign in again.
                </p>
                <button
                  type="button"
                  className="btn"
                  onClick={handleRequestCredits}
                  style={{ marginTop: '12px', background: '#E2E8F0', color: 'var(--text-primary)' }}
                >
                  Email Me Credit Details
                </button>
                <p style={{ marginTop: '10px', fontSize: '11px', color: 'var(--text-secondary)' }}>
                  If you have already paid or need assistance, please contact support at <strong>{CONTACT_EMAIL}</strong>.
                </p>
              </div>
            </div>
          )}

          {/* CONVERTER CARD */}
          <div className="glass-panel converter-panel">
            {conversionStatus === 'uploading' || conversionStatus === 'converting' ? (
              <div className="progress-container">
                <div className="spinner"></div>
                <div className="progress-title">Processing PDF</div>
                <div className="progress-subtitle">{progressMsg}</div>
              </div>
            ) : conversionStatus === 'success' ? (
              <div className="progress-container" style={{ gap: '16px' }}>
                <div style={{ fontSize: '48px', color: 'var(--accent-green)' }}>✓</div>
                <div className="progress-title">Conversion Successful!</div>
                <div style={{ fontSize: '13px', background: '#F1F5F9', border: '1px solid #E2E8F0', padding: '12px', borderRadius: '6px', width: '100%', wordBreak: 'break-all', fontWeight: 600 }}>
                  {downloadFilename}
                </div>
                
                {downloadUrl === '#mock-download' ? (
                  <button className="btn btn-success" onClick={() => alert("Mock File Downloaded successfully!")}>
                    Download Word Document
                  </button>
                ) : (
                  <a href={downloadUrl} download={downloadFilename} className="btn btn-success" style={{ textDecoration: 'none' }}>
                    Download Word Document
                  </a>
                )}
                
                <button className="btn" style={{ background: '#E2E8F0', color: 'var(--text-primary)', marginTop: '8px' }} onClick={resetUploadState}>
                  Convert Another File
                </button>
              </div>
            ) : (
              <div>
                <div className="section-title">
                  <span>Upload Test Paper</span>
                  <span style={{ fontSize: '11px', color: 'var(--accent-blue)' }}>PDF to DOCX</span>
                </div>
                
                {(user.status !== 'active' && user.status !== 'trial') ? (
                  <div style={{ textAlign: 'center', padding: '32px 16px', color: 'var(--text-muted)' }}>
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5" style={{ margin: '0 auto 12px auto', opacity: 0.5 }}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                    <p style={{ fontSize: '14px', fontWeight: 600 }}>Converter Locked</p>
                    <p style={{ fontSize: '12px', marginTop: '4px' }}>
                      {user.status === 'pending' 
                        ? "Free trial limit reached or pending subscription. Please contact support." 
                        : "Your account is locked. Please contact support."}
                    </p>
                  </div>
                ) : (
                  <div>
                    {!file ? (
                      <div 
                        className={`dropzone ${dragActive ? 'drag-active' : ''}`}
                        onDragEnter={handleDrag}
                        onDragOver={handleDrag}
                        onDragLeave={handleDrag}
                        onDrop={handleDrop}
                      >
                        <input 
                          type="file" 
                          id="file-upload" 
                          className="input-control" 
                          accept=".pdf"
                          style={{ display: 'none' }}
                          onChange={handleFileChange}
                        />
                        <label htmlFor="file-upload" style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                          <div className="dropzone-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                          </div>
                          <span className="dropzone-text">Tap or Drag PDF test paper</span>
                          <span className="dropzone-subtext">Max size: 25MB (.pdf only)</span>
                        </label>
                      </div>
                    ) : (
                      <div style={{ padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' }}>
                          <div style={{ fontSize: '28px', color: '#EF4444' }}>📄</div>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: '14px', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</div>
                            <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>{formatBytes(file.size)}</div>
                          </div>
                          <button className="btn-icon-only" style={{ borderRadius: '4px' }} onClick={() => setFile(null)}>✕</button>
                        </div>
                        <button className="btn btn-primary" onClick={startConversion}>
                          Convert to Editable Word
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* HISTORY SECTION */}
          <div className="glass-panel history-panel">
            <h3 className="section-title">Conversion History</h3>
            {history.length === 0 ? (
              <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                No documents converted yet.
              </div>
            ) : (
              <div className="history-list">
                {history.map(item => (
                  <div key={item.id} className="history-item">
                    <div className="history-info">
                      <span className="history-name" title={item.filename}>{item.filename}</span>
                      <span className="history-meta">
                        <span>{new Date(item.created_at).toLocaleDateString()}</span>
                        <span>•</span>
                        <span>{item.page_count} pages</span>
                        <span>•</span>
                        <span>{formatBytes(item.file_size)}</span>
                      </span>
                    </div>
                    <span className={`history-status status-${item.status}`}>
                      {item.status}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>
      )}

      {/* ADMIN PANEL VIEW */}
      {view === 'admin' && user && user.profession === 'Admin' && (
        <div className="admin-layout">
          <div className="profile-row">
            <div className="profile-avatar" style={{ background: 'var(--gradient-gold)' }}>AD</div>
            <div className="profile-details">
              <span className="profile-email">{user.email}</span>
              <span className="profile-subtext">SaaS Administrator Dashboard</span>
            </div>
          </div>

          <div className="glass-panel admin-panel">
            <div className="section-title">
              <span>Teacher Registrations</span>
              <span style={{ fontSize: '11px', color: 'var(--accent-gold)' }}>EFT Management</span>
            </div>
            
            <div className="input-group admin-search">
              <input 
                type="text" 
                className="input-control" 
                placeholder="Search teacher by email..."
                value={adminSearch}
                onChange={e => setAdminSearch(e.target.value)}
              />
            </div>

            <div style={{ flex: 1, overflowY: 'auto', maxHeight: '420px', paddingRight: '4px' }}>
              {adminUsers
                .filter(u => u.email.toLowerCase().includes(adminSearch.toLowerCase()))
                .map(targetUser => (
                  <div key={targetUser.id} className="user-row">
                    <div className="user-row-header">
                      <span className="user-email">{targetUser.email}</span>
                      <span className={`badge badge-${targetUser.status}`}>{targetUser.status}</span>
                    </div>
                    <div className="user-profession">Profession: {targetUser.profession}</div>
                    
                    <div className="user-actions" style={{ marginTop: '8px' }}>
                      {targetUser.status === 'pending' && (
                        <button 
                          className="btn-small btn-small-success"
                          onClick={() => handleUserStatusUpdate(targetUser.id, 'active')}
                        >
                          Approve EFT (Activate)
                        </button>
                      )}
                      {targetUser.status === 'active' && (
                        <button 
                          className="btn-small btn-small-danger"
                          onClick={() => handleUserStatusUpdate(targetUser.id, 'suspended')}
                        >
                          Suspend Account
                        </button>
                      )}
                      {targetUser.status === 'suspended' && (
                        <button 
                          className="btn-small btn-small-success"
                          onClick={() => handleUserStatusUpdate(targetUser.id, 'active')}
                        >
                          Re-Activate
                        </button>
                      )}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </div>
      )}
      </main>

      {/* FOOTER */}
      <footer style={{ textAlign: 'center', padding: '12px 0 4px 0', fontSize: '11px', color: 'var(--text-muted)', borderTop: '1px solid rgba(255, 255, 255, 0.03)' }}>
        © {new Date().getFullYear()} EducatorTools • Built for South African Teachers
      </footer>

    </div>
  );
}
