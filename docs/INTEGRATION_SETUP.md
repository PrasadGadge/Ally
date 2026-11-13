# Vivie AI — External Integration Setup Guide

This guide explains how to configure Vivie's external service integrations for Gmail, Calendar, and GitHub.

---

## Gmail and Calendar Integration

### Overview

Vivie uses Google OAuth 2.0 to access Gmail and Calendar. Tokens are stored locally and auto-refresh, so you only need to authorize once.

### Prerequisites

1. **Google Cloud Project**
   - Go to [console.cloud.google.com](https://console.cloud.google.com)
   - Create a new project or use an existing one
   - Enable the following APIs:
     - Gmail API
     - Google Calendar API

2. **OAuth Client Credentials**
   - Navigate to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth 2.0 Client ID**
   - Application type: **Desktop App**
   - Click **Create**
   - Download the JSON file (you don't need to save it)

3. **Copy Credentials to .env**
   - From the OAuth consent screen or credentials JSON, copy:
     - `client_id` (looks like: `xxx.apps.googleusercontent.com`)
     - `client_secret` (a random string)
   - Add them to your `.env` file:
     ```
     GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
     GOOGLE_CLIENT_SECRET=your_google_client_secret
     ```

### Authorization

Run the setup script to authorize Vivie:

```bash
python setup_mcp.py
```

This will:
1. Open your browser to Google's consent screen
2. Ask you to click "Allow"
3. Ask you to paste the authorization code back
4. Save tokens to `data/google_tokens.json`
5. Vivie can now access Gmail + Calendar indefinitely

### OAuth Scopes

Vivie requests the following Google scopes:
- `https://www.googleapis.com/auth/gmail.readonly` — Read emails
- `https://www.googleapis.com/auth/gmail.send` — Send emails
- `https://www.googleapis.com/auth/calendar.readonly` — Read calendar
- `https://www.googleapis.com/auth/calendar.events` — Create/modify events

### Token Storage

Tokens are stored in `data/google_tokens.json`:
- **Never commit this file** to version control
- It contains your refresh token and access token
- The file is excluded by `.gitignore`

### Token Refresh

Tokens auto-refresh when expired (1 hour lifetime). You should never need to re-authorize unless:
- You revoke access in your Google account settings
- You delete `data/google_tokens.json`
- You change your Google client credentials

### Revoking Access

To revoke Vivie's access:
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Navigate to **Third-party apps & services**
3. Find your OAuth client and remove it
4. Delete `data/google_tokens.json` from the Vivie project

### Troubleshooting

**"Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET"**
- Ensure both values are set in `.env`
- Ensure `.env` is in the project root directory
- Run `python setup_mcp.py` again

**"Authorization failed"**
- Ensure you copied the full authorization code
- Ensure your OAuth client is configured as "Desktop App"
- Ensure Gmail and Calendar APIs are enabled

**"Google not authorized" during runtime**
- Ensure `setup_mcp.py` completed successfully
- Check that `data/google_tokens.json` exists
- Ensure tokens haven't expired (should auto-refresh)

---

## GitHub Integration

### Overview

Vivie uses a GitHub Personal Access Token (classic) to access GitHub repositories.

### Prerequisites

1. **Generate Personal Access Token**
   - Go to [GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
   - Click **Generate new token (classic)**
   - Set the following scopes:
     - `repo` — Full repository access
     - `issues` — Issue and pull request access
     - `read:user` — Read user profile
   - Click **Generate token**
   - **Copy the token immediately** (you won't see it again)

2. **Add Token to .env**
   ```
   GITHUB_TOKEN=ghp_your_github_token_here
   GITHUB_USERNAME=your_github_username
   ```

### Token Permissions

Vivie's GitHub integration uses:
- **Read operations**: Repository info, issues, pull requests, file content
- **Write operations**: Not currently implemented (can be added with explicit approval)

### Security Notes

- **Never commit** your `.env` file to version control
- `.env` is excluded by `.gitignore`
- Rotate your token if it's ever compromised
- Tokens can be revoked at any time from GitHub settings

### Troubleshooting

**"GITHUB_TOKEN not set"**
- Ensure `GITHUB_TOKEN` is set in `.env`
- Ensure `.env` is in the project root directory

**"Insufficient permissions"**
- Ensure your token has the required scopes (`repo`, `issues`, `read:user`)
- Regenerate the token with correct scopes

**"Rate limit exceeded"**
- GitHub API has rate limits (5000 requests/hour for authenticated requests)
- Wait and retry, or increase the rate limit with a higher-tier account

---

## Web Search Integration

### Overview

Vivie uses Tavily API for web search with source citations.

### Prerequisites

1. **Get Tavily API Key**
   - Go to [tavily.com](https://tavily.com)
   - Sign up for an account
   - Get your API key from the dashboard

2. **Add Key to .env**
   ```
   TAVILY_API_KEY=your_tavily_api_key_here
   ```

### Features

- Search with source citations
- Publication date tracking
- Relevance scoring
- Source verification

### Troubleshooting

**"No search results found"**
- Ensure `TAVILY_API_KEY` is set in `.env`
- Check your Tavily API quota

---

## Configuration Checklist

Before running Vivie with external integrations, ensure:

- [ ] `.env` file exists in project root
- [ ] `GROQ_API_KEY` is set (required for STT)
- [ ] `NVIDIA_API_KEY` is set (required for LLM)
- [ ] `OPENROUTER_API_KEY` is set (required for advanced LLM)
- [ ] `WEATHER_API_KEY` is set (required for weather)
- [ ] Gmail/Calendar: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` set
- [ ] Gmail/Calendar: `python setup_mcp.py` run successfully
- [ ] GitHub: `GITHUB_TOKEN` and `GITHUB_USERNAME` set
- [ ] Web Search: `TAVILY_API_KEY` set

---

## Security Best Practices

1. **Never commit credentials** to version control
2. **Use environment variables** for all secrets
3. **Rotate tokens** periodically (GitHub, Google)
4. **Revoke access** for unused services
5. **Use least-privilege scopes** (don't request more than needed)
6. **Audit permissions** regularly in your service accounts

---

## Next Steps

After configuration:

1. Run validation:
   ```bash
   python validate_deps.py --health
   ```

2. Start Vivie:
   ```bash
   python Vivie.py
   ```

3. Test integrations:
   - "Check my emails" (Gmail)
   - "What's on my calendar today?" (Calendar)
   - "Check issues in my repository" (GitHub)
   - "Search for information about X" (Web Search)

---

## Support

For issues with:
- **Gmail/Calendar**: Check Google Cloud Console and OAuth settings
- **GitHub**: Check GitHub token permissions and rate limits
- **Web Search**: Check Tavily API key and quota
- **General**: Check `.env` configuration and run `python validate_deps.py`
