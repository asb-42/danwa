<!-- LoginView.svelte — Login / Register form -->

<script>
  import { login, register } from '../lib/auth.js';
  import { isAuthenticated } from '../lib/stores/auth.svelte.js';
  import { route } from '../lib/stores.js';

  let email = $state('');
  let displayName = $state('');
  let password = $state('');
  let confirmPassword = $state('');
  let isRegisterMode = $state(false);
  let error = $state('');
  let loading = $state(false);

  // Redirect to dashboard if already authenticated
  $effect(() => {
    if ($isAuthenticated) {
      route.set('dashboard');
    }
  });

  async function handleSubmit(e) {
    e.preventDefault();
    error = '';
    loading = true;

    try {
      if (isRegisterMode) {
        if (password !== confirmPassword) {
          error = 'Passwords do not match';
          loading = false;
          return;
        }
        await register(email, displayName || email.split('@')[0], password);
        // Auto-login after registration
        await login(email, password);
      } else {
        await login(email, password);
      }
      route.set('dashboard');
    } catch (err) {
      error = err.message || 'Authentication failed';
    } finally {
      loading = false;
    }
  }

  function toggleMode() {
    isRegisterMode = !isRegisterMode;
    error = '';
  }
</script>

<div class="login-container">
  <div class="login-card">
    <h1 class="login-title">
      {isRegisterMode ? 'Create Account' : 'Sign In'}
    </h1>
    <p class="login-subtitle">
      {isRegisterMode ? 'Create a new account to get started' : 'Welcome back to Danwa'}
    </p>

    {#if error}
      <div class="error-banner">{error}</div>
    {/if}

    <form onsubmit={handleSubmit}>
      <div class="form-group">
        <label for="email">Email</label>
        <input
          id="email"
          type="email"
          bind:value={email}
          placeholder="you@example.com"
          required
          autocomplete="email"
        />
      </div>

      {#if isRegisterMode}
        <div class="form-group">
          <label for="displayName">Display Name</label>
          <input
            id="displayName"
            type="text"
            bind:value={displayName}
            placeholder="Your name"
            autocomplete="name"
          />
        </div>
      {/if}

      <div class="form-group">
        <label for="password">Password</label>
        <input
          id="password"
          type="password"
          bind:value={password}
          placeholder={isRegisterMode ? 'At least 8 characters' : 'Your password'}
          required
          minlength="8"
          autocomplete={isRegisterMode ? 'new-password' : 'current-password'}
        />
      </div>

      {#if isRegisterMode}
        <div class="form-group">
          <label for="confirmPassword">Confirm Password</label>
          <input
            id="confirmPassword"
            type="password"
            bind:value={confirmPassword}
            placeholder="Repeat your password"
            required
            minlength="8"
            autocomplete="new-password"
          />
        </div>
      {/if}

      <button type="submit" class="btn-primary" disabled={loading}>
        {#if loading}
          <span class="spinner"></span>
        {:else}
          {isRegisterMode ? 'Create Account' : 'Sign In'}
        {/if}
      </button>
    </form>

    <p class="toggle-mode">
      {isRegisterMode ? 'Already have an account?' : "Don't have an account?"}
      <button type="button" class="link-btn" onclick={toggleMode}>
        {isRegisterMode ? 'Sign In' : 'Create one'}
      </button>
    </p>
  </div>
</div>

<style>
  .login-container {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: var(--color-bg, #f5f5f5);
    padding: 1rem;
  }

  .login-card {
    background: var(--color-surface, #fff);
    border-radius: 12px;
    padding: 2.5rem;
    width: 100%;
    max-width: 400px;
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
  }

  .login-title {
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0 0 0.25rem;
    color: var(--color-text, #1a1a1a);
  }

  .login-subtitle {
    color: var(--color-text-secondary, #666);
    margin: 0 0 1.5rem;
    font-size: 0.95rem;
  }

  .error-banner {
    background: #fee;
    color: #c00;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    margin-bottom: 1rem;
    font-size: 0.9rem;
    border: 1px solid #fcc;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group label {
    display: block;
    font-weight: 600;
    margin-bottom: 0.35rem;
    color: var(--color-text, #1a1a1a);
    font-size: 0.9rem;
  }

  .form-group input {
    width: 100%;
    padding: 0.65rem 0.75rem;
    border: 1px solid var(--color-border, #ddd);
    border-radius: 8px;
    font-size: 0.95rem;
    background: var(--color-surface, #fff);
    color: var(--color-text, #1a1a1a);
    box-sizing: border-box;
    transition: border-color 0.15s;
  }

  .form-group input:focus {
    outline: none;
    border-color: var(--color-primary, #3b82f6);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
  }

  .btn-primary {
    width: 100%;
    padding: 0.75rem;
    background: var(--color-primary, #3b82f6);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    margin-top: 0.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    transition: background 0.15s;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--color-primary-hover, #2563eb);
  }

  .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .spinner {
    width: 18px;
    height: 18px;
    border: 2px solid rgba(255, 255, 255, 0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.6s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .toggle-mode {
    text-align: center;
    margin-top: 1.25rem;
    color: var(--color-text-secondary, #666);
    font-size: 0.9rem;
  }

  .link-btn {
    background: none;
    border: none;
    color: var(--color-primary, #3b82f6);
    cursor: pointer;
    font-weight: 600;
    font-size: 0.9rem;
    text-decoration: underline;
    padding: 0;
  }

  .link-btn:hover {
    color: var(--color-primary-hover, #2563eb);
  }
</style>
