# Security and Environment Configuration Standards

## Core Principle

**NEVER hardcode sensitive values or enable debug features in production. ALL security-sensitive configurations must be controlled by environment variables with secure defaults.**

## Environment Variable Standards

### 1. Debug and Development Features

- **Debug Modes**: Always controlled by environment variables (e.g., `FLASK_DEBUG`, `NODE_ENV`)
- **Default to Secure**: Debug modes must default to `False`/`production` for safety
- **Multiple True Values**: Accept multiple formats: 'true', '1', 'yes', 'on' (case-insensitive)
- **Production Safety**: Ensure debug features cannot accidentally be enabled in production

```python
# CORRECT - Environment controlled debug mode
debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() in ('true', '1', 'yes', 'on')
app.run(debug=debug_mode)

# WRONG - Hardcoded debug mode
app.run(debug=True)  # Never hardcode True in production code
```

### 2. Secret Generation and Management

- **Consistent Entropy**: All generated secrets must have consistent, adequate length (minimum 32 characters)
- **Cryptographically Secure**: Use proper random generation (OpenSSL, cryptographic libraries)
- **No Weak Defaults**: Never use placeholder values like "changeme" or simple strings
- **Centralized Storage**: Use key management services (Azure Key Vault, AWS Secrets Manager)

```bash
# CORRECT - Consistent 32-character secrets
SECRET_KEY=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
JWT_SECRET_KEY=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
NEO4J_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

# WRONG - Inconsistent lengths or weak secrets  
NEO4J_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)  # Too short
SECRET_KEY="changeme"  # Weak placeholder
```

### 3. Configuration File Standards

- **No Secrets in Code**: Never commit secrets or API keys to version control
- **Environment Templates**: Provide .env.example files with placeholder values
- **Documentation**: Document all environment variables with descriptions and defaults
- **Validation**: Validate required environment variables on application startup

### 4. Deprecation and Backward Compatibility

- **Clear Marking**: Use "DEPRECATED" prefix in comments and documentation
- **Migration Instructions**: Provide step-by-step migration guidance
- **Compatibility Logic**: Handle both old and new configurations gracefully
- **Timeline Communication**: Document when features will be removed

```python
# CORRECT - Clear deprecation documentation
industry: Optional[str] = None  # DEPRECATED: Use 'industries' instead. Retained for backward compatibility with legacy data/models. If both 'industry' and 'industries' are provided, 'industry' is added to 'industries' if not present. New code should use 'industries' (a list of strings) for all cases. Migrate existing data by moving the value of 'industry' into 'industries' and removing 'industry'.
industries: Optional[List[str]] = None  # Multiple industries support; preferred field for all new code and data.
```

## Security Validation Checklist

### Before Deployment

- [ ] No hardcoded debug=True in production code
- [ ] All secrets generated with adequate entropy (≥32 characters)
- [ ] Environment variables have secure defaults
- [ ] No sensitive values in version control
- [ ] Key Vault/secret management properly configured
- [ ] Deprecated features properly documented with migration paths

### Code Review Requirements

- [ ] Check for inline debug flags or development settings
- [ ] Verify secret generation uses consistent lengths
- [ ] Ensure environment variables control security-sensitive features
- [ ] Validate that defaults are production-safe
- [ ] Review deprecation documentation for completeness

## Common Anti-Patterns to Avoid

1. **Hardcoded Debug Modes**: `app.run(debug=True)` in main application files
2. **Inconsistent Secret Lengths**: Some secrets 25 chars, others 32 chars
3. **Weak Placeholders**: Using "password", "secret", "changeme" as defaults
4. **Missing Environment Control**: Security features not configurable via environment
5. **Insufficient Documentation**: Deprecation without migration guidance

This skill ensures enterprise-grade security practices and proper environment management across all application components.
