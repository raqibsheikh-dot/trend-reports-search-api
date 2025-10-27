# 🔒 SECURITY NOTICE - API Key Rotation Required

**Date**: 2025-10-26
**Severity**: HIGH
**Status**: ACTION REQUIRED

## Issue

An API key was found hardcoded in `backend/test_commands.sh` and committed to git history:
```
API_KEY="s1RVpbfkU6NhaCOvw4v_PX7vmoFb9O3YOOBIKXbd-lk"
```

## Actions Taken

1. ✅ Removed hardcoded key from `test_commands.sh`
2. ✅ Updated script to require API_KEY environment variable
3. ✅ Added validation to prevent running without key

## Required Actions

### 🚨 IMMEDIATE (Within 24 hours)

1. **Rotate the API Key**
   ```bash
   cd backend
   # Generate new secure API key
   openssl rand -hex 32

   # Update .env file with new key
   # API_KEY=<new_key_here>
   ```

2. **Update All Deployments**
   - Render.com: Update API_KEY environment variable
   - Local development: Update `.env` file
   - CI/CD: Update secrets
   - Any shared team environments

3. **Notify Team Members**
   - Inform all developers to update their local `.env` files
   - Update any documentation with the old key

### 📋 Optional (Recommended)

4. **Remove from Git History** (if repository is public or shared)
   ```bash
   # This rewrites git history - coordinate with team first!
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch backend/test_commands.sh' \
     --prune-empty --tag-name-filter cat -- --all

   # Force push to remove from remote
   git push origin --force --all
   git push origin --force --tags
   ```

5. **Audit API Usage**
   - Check API logs for unauthorized access
   - Review recent API calls for suspicious activity
   - Monitor for unexpected usage patterns

6. **Implement Key Rotation Policy**
   - Rotate API keys every 90 days
   - Use secrets manager (AWS Secrets Manager, HashiCorp Vault)
   - Implement key versioning for gradual rotation

## Prevention

Going forward:

1. ✅ Never commit API keys to git
2. ✅ Use environment variables exclusively
3. ✅ Add `*.env` to `.gitignore`
4. ✅ Use `.env.example` with placeholder values
5. ✅ Enable git pre-commit hooks to scan for secrets
6. ✅ Use tools like `git-secrets` or `trufflehog`

## Test After Rotation

After rotating the key:

```bash
# Test with new key
export API_KEY=<new_key_here>
./backend/test_commands.sh http://localhost:8000

# Test on production
export API_KEY=<new_key_here>
./backend/test_commands.sh https://trend-reports-api.onrender.com
```

## Questions?

If you have questions or need help with key rotation, refer to:
- `backend/.env.example` for configuration
- `backend/README.md` for setup instructions
- `COMPREHENSIVE_CODE_REVIEW_REPORT.md` for security details

---

**Priority**: 🔴 HIGH - Complete within 24 hours
**Tracking**: Log completion in git commit message when done
