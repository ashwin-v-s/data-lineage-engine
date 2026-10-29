(() => {
  const authScreen = document.getElementById('authScreen');
  const appShell = document.querySelector('.app-shell');
  const frame = document.getElementById('authFrame');
  const sessionKey = 'kairos_supabase_session';
  const appScripts = [
    'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js',
    'https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js',
    '/observatory.js?v=304',
    '/stewardship.js?v=304',
    '/app.js?v=305',
    '/pii-lineage-enhancements.js?v=304',
  ];
  let config = null;
  let configLoaded = false;
  let activeSession = null;
  let refreshTimer = null;
  let appStarted = false;

  const trustedProviders = new Set(['google', 'github', 'azure']);
  const hasActiveSession = () => Boolean(activeSession?.access_token
    && (!activeSession.expires_at || activeSession.expires_at * 1000 > Date.now())
    && (!activeSession.kairos_remember_until || activeSession.kairos_remember_until > Date.now()));

  const readSaved = () => {
    for (const storage of [localStorage, sessionStorage]) {
      try {
        const value = JSON.parse(storage.getItem(sessionKey) || 'null');
        if (value?.access_token) return value;
      } catch (_) { /* Ignore invalid local session state. */ }
    }
    return null;
  };
  const saveSession = (value, remember = false) => {
    const target = remember ? localStorage : sessionStorage;
    const other = target === localStorage ? sessionStorage : localStorage;
    const session = { ...value };
    if (!session.expires_at && session.expires_in) session.expires_at = Math.floor(Date.now() / 1000) + Number(session.expires_in);
    if (remember) {
      session.kairos_remember_until ||= Date.now() + 30 * 24 * 60 * 60 * 1000;
    } else {
      delete session.kairos_remember_until;
    }
    target.setItem(sessionKey, JSON.stringify(session));
    other.removeItem(sessionKey);
    activeSession = session;
    scheduleRefresh(session);
    return session;
  };
  const clearSession = () => {
    localStorage.removeItem(sessionKey);
    sessionStorage.removeItem(sessionKey);
    // Browser-local profile values are user-specific; don't leave them visible
    // when this browser is signed out or used by another account.
    localStorage.removeItem('kairos_profileName');
    localStorage.removeItem('kairos_profilePicture');
    localStorage.removeItem('kairos_workspaceLabel');
    clearTimeout(refreshTimer);
    activeSession = null;
  };
  async function authRequest(path, body, accessToken) {
    const headers = { apikey: config.publishable_key, 'Content-Type': 'application/json' };
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
    const response = await fetch(`${config.url}/auth/v1/${path}`, {
      method: 'POST', headers, body: body ? JSON.stringify(body) : undefined,
    });
    const result = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(result.msg || result.message || result.error_description || result.error || `Authentication failed (${response.status}).`);
    return result;
  }
  function frameStatus(form, ok, message, mode) {
    frame?.contentWindow?.postMessage({ source: 'kairos-auth-host', form, ok, message, mode }, location.origin);
  }
  function sendCurrentUserToFrame() {
    if (hasActiveSession() && activeSession.user?.email) {
      frame?.contentWindow?.postMessage({ source: 'kairos-auth-host', control: 'session-user', email: activeSession.user.email }, location.origin);
    }
  }
  function setAuthAnimationPaused(paused) {
    frame?.contentWindow?.postMessage({ source: 'kairos-auth-host', control: paused ? 'pause-animation' : 'resume-animation' }, location.origin);
  }
  function showAuthError(message) {
    if (!frame?.contentWindow) return;
    frameStatus('signin', false, message || 'Authentication is not configured for this Kairos server.');
  }
  async function refreshSession(session) {
    if (!session?.refresh_token || !config?.url || !config?.publishable_key) throw new Error('Your sign-in has expired. Please sign in again.');
    if (session.kairos_remember_until && session.kairos_remember_until <= Date.now()) {
      clearSession();
      throw new Error('Your remembered session expired. Please sign in again.');
    }
    const remember = Boolean(localStorage.getItem(sessionKey));
    const next = await authRequest('token?grant_type=refresh_token', { refresh_token: session.refresh_token });
    if (session.user && !next.user) next.user = session.user;
    if (session.kairos_remember_until) next.kairos_remember_until = session.kairos_remember_until;
    return saveSession(next, remember);
  }
  function scheduleRefresh(session) {
    clearTimeout(refreshTimer);
    if (!session?.expires_at || !session.refresh_token) return;
    const delay = Math.max(5_000, session.expires_at * 1000 - Date.now() - 60_000);
    refreshTimer = setTimeout(async () => {
      try { await refreshSession(activeSession); }
      catch (_) { clearSession(); location.replace('/'); }
    }, Math.min(delay, 2_147_000_000));
  }
  function installApiAuthorization() {
    if (window.__kairosBearerFetch) return;
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input, init = {}) => {
      const url = typeof input === 'string' ? input : input?.url || '';
      if (!url.startsWith('/api/v1/') && !url.startsWith('/ingestion.html')) return originalFetch(input, init);
      if (window.kairosDemoPreview) {
        const isIngestion = url.startsWith('/ingestion.html');
        return new Response(isIngestion ? 'Demo preview cannot access ingestion.' : JSON.stringify({ ok: false, error: { message: 'Demo preview cannot access the catalog.' } }), { status: 403, headers: { 'Content-Type': isIngestion ? 'text/plain' : 'application/json' } });
      }
      let session = activeSession || readSaved();
      if (session?.expires_at && session.expires_at * 1000 < Date.now() + 20_000) {
        try { session = await refreshSession(session); } catch (_) { clearSession(); session = null; }
      }
      const headers = new Headers(init.headers || (input instanceof Request ? input.headers : undefined));
      if (session?.access_token) headers.set('Authorization', `Bearer ${session.access_token}`);
      const response = await originalFetch(input, { ...init, headers });
      if (response.status === 401 && session?.access_token) {
        clearSession();
        location.replace('/');
      }
      return response;
    };
    window.__kairosBearerFetch = true;
  }
  async function restoreSession() {
    let session = readSaved();
    if (!session) return null;
    if (session.kairos_remember_until && session.kairos_remember_until <= Date.now()) {
      clearSession();
      return null;
    }
    if (session.expires_at && session.expires_at * 1000 < Date.now() + 30_000) session = await refreshSession(session);
    const response = await fetch(`${config.url}/auth/v1/user`, { headers: { apikey: config.publishable_key, Authorization: `Bearer ${session.access_token}` } });
    if (response.status === 401 || response.status === 403) { clearSession(); return null; }
    if (!response.ok) throw new Error('Supabase could not validate the saved session.');
    session.user = await response.json();
    saveSession(session, Boolean(localStorage.getItem(sessionKey)));
    return session;
  }
  async function loadAppScripts(index = 0) {
    if (index >= appScripts.length) return;
    await new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = appScripts[index];
      script.onload = resolve;
      script.onerror = () => reject(new Error(`Could not load ${appScripts[index]}`));
      document.body.appendChild(script);
    });
    return loadAppScripts(index + 1);
  }
  function addSignOut(session) {
    const row = document.querySelector('.user-row');
    if (!row || document.getElementById('kairosSignOut')) return;
    const button = document.createElement('button');
    button.id = 'kairosSignOut';
    button.className = 'auth-link';
    button.type = 'button';
    button.textContent = window.kairosDemoPreview ? 'Exit demo preview' : 'Sign out';
    button.style.margin = '10px 18px';
    button.addEventListener('click', signOut);
    row.insertAdjacentElement('afterend', button);
    if (session?.user?.email) {
      document.querySelectorAll('.profile-display-name').forEach(el => {
        if (el.textContent === 'Jatin Shende' || el.textContent === 'Workspace user') el.textContent = session.user.email;
      });
      window.kairosUser = { id: session.user.id || '', email: session.user.email || '' };
    }
  }
  async function signOut() {
    if (window.kairosDemoPreview) {
      window.kairosDemoPreview = false;
      location.replace('/');
      return;
    }
    try { await authRequest('logout', null, activeSession?.access_token); } catch (_) { /* Clear the local session even if remote logout is unreachable. */ }
    clearSession();
    location.replace('/');
  }
  async function startApp(session, { demoPreview = false } = {}) {
    window.kairosDemoPreview = Boolean(demoPreview);
    if (session?.access_token) {
      activeSession = session;
      scheduleRefresh(session);
    }
    const authUser = session?.user;
    window.kairosUser = authUser ? { id: authUser.id || '', email: authUser.email || '' } : null;
    if (authUser) {
      const metadata = authUser.user_metadata || {};
      const accountName = String(metadata.full_name || metadata.name || authUser.email || 'Workspace user').trim();
      const currentName = localStorage.getItem('kairos_profileName');
      if (!currentName || currentName === 'Jatin Shende' || currentName === 'Workspace user') {
        localStorage.setItem('kairos_profileName', accountName);
      }
      const currentWorkspaceLabel = localStorage.getItem('kairos_workspaceLabel');
      if (!currentWorkspaceLabel || currentWorkspaceLabel === 'Research workspace') {
        localStorage.setItem('kairos_workspaceLabel', 'Personal workspace');
      }
    }
    installApiAuthorization();
    authScreen.hidden = true;
    appShell.hidden = false;
    if (appStarted) return;
    appStarted = true;
    try {
      await loadAppScripts();
      addSignOut(session);
      setAuthAnimationPaused(true);
      document.addEventListener('click', event => {
        if (event.target.closest('#kairosAuthPageSignOut')) document.getElementById('kairosSignOut')?.click();
      });
      document.getElementById('dataModeSelect')?.remove();
      document.addEventListener('click', event => {
        const link = event.target.closest('a[href="/ingestion.html"]');
        if (!link) return;
        event.preventDefault();
        serveIngestion(activeSession).catch(error => window.alert(error.message));
      });
    } catch (error) {
      appStarted = false;
      appShell.hidden = true;
      authScreen.hidden = false;
      frameStatus('signin', false, `Kairos could not load the dashboard: ${error.message}`);
    }
  }
  async function beginOAuth(provider) {
    if (!trustedProviders.has(provider)) throw new Error('This identity provider is not enabled in Kairos.');
    const query = new URLSearchParams({ provider, redirect_to: location.origin });
    location.assign(`${config.url}/auth/v1/authorize?${query}`);
  }
  async function handleFrameMessage(event) {
    if (event.origin !== location.origin || event.source !== frame?.contentWindow) return;
    const message = event.data;
    if (!message || message.source !== 'kairos-auth-stitch') return;
    if (message.type === 'demo-preview') {
      await startApp(null, { demoPreview: true });
      return;
    }
    if (message.type === 'ready') {
      if (configLoaded && (!config?.url || !config?.publishable_key)) frameStatus('signin', false, 'Supabase sign-in is not configured. Set the project URL and publishable key on the server.');
      sendCurrentUserToFrame();
      return;
    }
    try {
      if (!config?.url || !config?.publishable_key) throw new Error('Supabase sign-in is not configured on this server.');
      if (message.type === 'signin') {
        const session = await authRequest('token?grant_type=password', { email: message.email, password: message.password });
        saveSession(session, Boolean(message.remember));
        await startApp(session);
      } else if (message.type === 'signup') {
        const redirectTo = `${location.origin}/`;
        const result = await authRequest(`signup?redirect_to=${encodeURIComponent(redirectTo)}`, { email: message.email, password: message.password, data: { full_name: message.name, department: message.role, terms_accepted: true, terms_accepted_at: new Date().toISOString() } });
        if (result.access_token && result.user?.email_confirmed_at) {
          saveSession(result);
          await startApp(result);
        } else {
          if (result.access_token) {
            try { await authRequest('logout', null, result.access_token); } catch (_) { /* Do not retain a session for an unverified signup. */ }
          }
          frameStatus('signup', true, `Account created for ${message.email}. Supabase sent a verification link to your work email. Verify it before signing in.`, 'signin');
        }
      } else if (message.type === 'recover') {
        const recoverUrl = new URL(`${config.url}/auth/v1/recover`);
        recoverUrl.searchParams.set('redirect_to', `${location.origin}/`);
        const response = await fetch(recoverUrl, { method: 'POST', headers: { apikey: config.publishable_key, 'Content-Type': 'application/json' }, body: JSON.stringify({ email: message.email }) });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.msg || result.message || `Password recovery failed (${response.status}).`);
        frameStatus('recover', true, 'If this email has a Kairos account, Supabase will send a password reset link.');
      } else if (message.type === 'oauth') {
        if (!trustedProviders.has(message.provider)) throw new Error('This identity provider is not enabled in Kairos.');
        await beginOAuth(message.provider);
      }
    } catch (error) {
      frameStatus(message.type, false, error.message || 'Authentication could not be completed. Please try again.');
    }
  }
  async function consumeOAuthCallback() {
    if (!config?.url || !config?.publishable_key) return null;
    const values = new URLSearchParams(location.hash.slice(1));
    const queryValues = new URLSearchParams(location.search);
    const authError = values.get('error_description') || values.get('error') || queryValues.get('error_description') || queryValues.get('error');
    if (authError) { history.replaceState(null, '', location.pathname); throw new Error(authError.replace(/\+/g, ' ')); }
    if (!location.hash) return null;
    const token = values.get('access_token');
    if (!token) return null;
    history.replaceState(null, '', `${location.pathname}${location.search}`);
    const response = await fetch(`${config.url}/auth/v1/user`, { headers: { apikey: config.publishable_key, Authorization: `Bearer ${token}` } });
    const user = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(user.msg || user.message || 'The identity provider returned an invalid session.');
    const session = saveSession({ access_token: token, refresh_token: values.get('refresh_token'), expires_in: Number(values.get('expires_in') || 3600), user });
    return { session, type: values.get('type') || '' };
  }
  function showPasswordReset(session) {
    authScreen.hidden = false;
    authScreen.innerHTML = `<section class="auth-card"><div class="auth-brand"><img src="/logo.png" alt=""><span>KAIROS</span></div><h1>Set a new password</h1><p class="auth-subtitle">Choose a new password for your Kairos account.</p><form id="passwordResetForm" class="auth-form"><label>New password<input name="password" type="password" autocomplete="new-password" minlength="8" required></label><p id="passwordResetMessage" class="auth-message" role="status" aria-live="polite"></p><button class="auth-primary" type="submit">Update password</button></form></section>`;
    document.getElementById('passwordResetForm').addEventListener('submit', async event => {
      event.preventDefault();
      const button = event.currentTarget.querySelector('button[type="submit"]');
      const message = document.getElementById('passwordResetMessage');
      button.disabled = true;
      try {
        const response = await fetch(`${config.url}/auth/v1/user`, {
          method: 'PUT',
          headers: { apikey: config.publishable_key, Authorization: `Bearer ${session.access_token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: new FormData(event.currentTarget).get('password') }),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(result.msg || result.message || `Password update failed (${response.status}).`);
        message.textContent = 'Password updated. Opening your Kairos workspace…';
        message.classList.add('success');
        await startApp(session);
      } catch (error) {
        message.textContent = error.message || 'Password could not be updated.';
        button.disabled = false;
      }
    });
  }
  async function serveIngestion(session) {
    activeSession = session;
    installApiAuthorization();
    scheduleRefresh(session);
    const response = await fetch('/ingestion.html');
    if (!response.ok) throw new Error('The ingestion page could not be loaded.');
    document.open();
    document.write(await response.text());
    document.close();
    const header = document.querySelector('.ingest-head');
    if (header) {
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'btn'; button.textContent = 'Sign out';
      button.addEventListener('click', signOut);
      header.appendChild(button);
    }
  }
  async function boot() {
    window.addEventListener('message', handleFrameMessage);
    try {
      const response = await fetch('/api/v1/auth/config', { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error('Could not read authentication configuration.');
      config = await response.json();
      configLoaded = true;
      if (!config?.url || !config?.publishable_key) {
        authScreen.hidden = false;
        setTimeout(() => showAuthError('Supabase sign-in is not configured. Add the project URL and publishable key to the server environment.'), 250);
        return;
      }
      const oauthResult = await consumeOAuthCallback();
      if (oauthResult?.session) {
        if (oauthResult.type === 'recovery') { showPasswordReset(oauthResult.session); return; }
        await startApp(oauthResult.session); return;
      }
      const session = await restoreSession();
      if (session) {
        if (location.pathname === '/ingestion.html' || location.pathname === '/ingestion/') {
          await serveIngestion(session);
          return;
        }
        await startApp(session);
        return;
      }
      if (location.pathname !== '/') { location.replace(`/?return_to=${encodeURIComponent(location.pathname)}`); return; }
      authScreen.hidden = false;
    } catch (error) {
      authScreen.hidden = false;
      setTimeout(() => showAuthError(error.message || 'Could not read the Supabase authentication settings.'), 250);
    }
  }
  boot();
})();
