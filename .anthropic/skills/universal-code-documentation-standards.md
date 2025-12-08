# Universal Code Documentation Standards

## Core Principle

**ALWAYS maintain up-to-date documentation when creating or modifying code. Documentation must be updated simultaneously with code changes.**

## Universal Documentation Requirements

### 1. File/Module Documentation

- **Purpose**: What the file/module does and its role in the application
- **Dependencies**: External libraries, frameworks, or modules required
- **Public Interface**: Main classes, functions, or exports
- **Usage Examples**: How to import and use the module

### 2. Class/Component Documentation  

- **Purpose**: What the class represents and its responsibilities
- **Properties/State**: All properties with types and descriptions
- **Methods/Functions**: All methods with parameters, return types, and behavior
- **Usage Examples**: Code examples showing instantiation and common usage
- **Lifecycle**: For components, document lifecycle methods and hooks

### 3. Function/Method Documentation

- **Purpose**: Clear explanation of what the function does
- **Parameters**: All parameters with types, descriptions, and default values
- **Return Value**: Return type and what it represents
- **Side Effects**: State changes, API calls, or other side effects
- **Error Conditions**: Exceptions, error codes, or failure scenarios
- **Complexity**: Time/space complexity for algorithms

### 4. API/Interface Documentation

- **Endpoints**: HTTP methods, URLs, and purposes
- **Request Format**: Body structure, headers, query parameters
- **Response Format**: Success and error response structures
- **Authentication**: Required tokens, API keys, or credentials
- **Rate Limits**: Usage limitations and quotas
- **Examples**: Complete request/response examples

### 5. Deprecation and Migration Documentation

- **Deprecation Notice**: Clear marking of deprecated features with "DEPRECATED" prefix
- **Migration Path**: Step-by-step instructions for moving to replacement functionality
- **Timeline**: When the feature was deprecated and when it will be removed
- **Backward Compatibility**: How legacy data/code will be handled during transition
- **Examples**: Code samples showing both old and new approaches

### 6. Security and Environment Configuration

- **Environment Variables**: Document all configuration options with secure defaults
- **Secret Management**: Guidelines for handling sensitive configuration
- **Production Safety**: Ensure debug modes and development features are controlled by environment
- **Default Values**: Always specify secure defaults that prevent accidental exposure

## File and Folder Naming Standards

### Documentation Files

- **Project README**: Use GitHub convention README.md (capitalized) for main project documentation
- **Other markdown files**: Use lowercase with hyphens (user-guide.md, api-reference.md)
- **Documentation folder**: Always use 'docs' folder when possible
- **Location**: Place documentation files in /docs/ folder for centralized access
- **Structure**: Organize by topic with clear folder hierarchy

### Markdown Formatting Standards

- **Code Blocks**: Always specify language for syntax highlighting (```python,```bash, ```json)
- **Line Spacing**: Add blank lines before and after headers, code blocks, and lists
- **Line Endings**: End all lines with two spaces for proper line breaks when needed  
- **Headers**: Use proper hierarchy (# > ## > ### > ####) with blank lines before/after
- **Lists**: Add blank lines before and after list blocks for readability
- **Links**: Use descriptive text, not "click here" or raw URLs
- **Code Inline**: Use backticks for `inline code` and file names
- **Emphasis**: Use **bold** for important terms, *italic* for emphasis

### Markdown Structure Examples

**Correct Markdown Formatting:**

```markdown
# Main Title

Brief introduction paragraph with proper spacing.

## Section Header

Content paragraph explaining the section.

### Subsection

Important points to remember:

- First list item with proper spacing  
- Second list item  
- Third list item  

Code example with language specified:

```python
def example_function():
    return "Hello, World!"
```

More content follows with proper blank line separation.

## Next Section

Continue with consistent structure and spacing.

```txt

**File Organization:**

```txt
README.md                   # Main project documentation (GitHub convention)
docs/
├── readme.md              # Additional documentation (lowercase)
├── api-reference.md       # API documentation
├── user-guide.md          # User documentation
├── deployment-guide.md    # Deployment instructions
└── development/
    ├── setup.md           # Development setup
    └── contributing.md    # Contribution guidelines
```

## Documentation Formats by Language

### Python (Docstrings)

```python
def calculate_similarity(text1: str, text2: str, algorithm: str = "cosine") -> float:
    """
    Calculate text similarity using specified algorithm.
    
    Computes similarity score between two text strings using various
    algorithms including cosine similarity, Jaccard index, or Levenshtein.
    
    Args:
        text1 (str): First text string to compare
        text2 (str): Second text string to compare
        algorithm (str, optional): Similarity algorithm to use. 
            Options: 'cosine', 'jaccard', 'levenshtein'. Defaults to 'cosine'.
            
    Returns:
        float: Similarity score between 0.0 and 1.0, where 1.0 indicates
            identical texts and 0.0 indicates completely different texts.
            
    Raises:
        ValueError: If algorithm is not supported
        TypeError: If inputs are not strings
        
    Example:
        >>> calculate_similarity("hello world", "hello there", "cosine")
        0.7071067811865476
        
    Note:
        Cosine similarity is recommended for longer texts, while Levenshtein
        is better for short strings with typos.
    """
```

### JavaScript/TypeScript (JSDoc)

```javascript
/**
 * Validates and processes user input data
 * @async
 * @param {Object} userData - User data to validate
 * @param {string} userData.email - User email address
 * @param {string} userData.password - User password (min 8 characters)
 * @param {string} [userData.name] - Optional user display name
 * @param {Object} [options] - Validation options
 * @param {boolean} [options.strict=false] - Enable strict validation rules
 * @param {string[]} [options.allowedDomains] - Whitelist of email domains
 * @returns {Promise<ProcessedUser>} Processed and validated user object
 * @throws {ValidationError} When validation fails
 * @throws {NetworkError} When external validation service is unavailable
 * @example
 * // Basic usage
 * const user = await validateUserData({
 *   email: 'user@example.com',
 *   password: 'securepass123'
 * });
 * 
 * @example
 * // With options
 * const user = await validateUserData(userData, {
 *   strict: true,
 *   allowedDomains: ['company.com', 'partner.com']
 * });
 * @since 2.1.0
 */
async function validateUserData(userData, options = {}) {
    // Implementation
}
```

### Java (JavaDoc)

```java
/**
 * Service for managing user authentication and authorization.
 * 
 * <p>This service provides methods for user login, logout, token validation,
 * and role-based access control. It integrates with external OAuth providers
 * and maintains session state.
 * 
 * <p>Usage example:
 * <pre>{@code
 * AuthService auth = new AuthService(config);
 * UserToken token = auth.authenticate("user@example.com", "password");
 * boolean hasAccess = auth.hasRole(token, Role.ADMIN);
 * }</pre>
 * 
 * @author Development Team
 * @version 1.3.0
 * @since 1.0.0
 */
public class AuthService {
    /**
     * Authenticates user with email and password.
     * 
     * @param email the user's email address, must be valid format
     * @param password the user's password, must meet complexity requirements
     * @return UserToken containing authentication details and permissions
     * @throws AuthenticationException if credentials are invalid
     * @throws ServiceUnavailableException if authentication service is down
     * @see UserToken
     * @since 1.0.0
     */
    public UserToken authenticate(String email, String password) {
        // Implementation
    }
}
```

### C# (XML Documentation)

```csharp
/// <summary>
/// Represents a document processor for redaction operations.
/// </summary>
/// <remarks>
/// This class handles various document formats including PDF, Word, and images.
/// It uses machine learning models for intelligent pattern detection and
/// supports custom redaction rules.
/// </remarks>
/// <example>
/// <code>
/// var processor = new DocumentProcessor();
/// var result = await processor.ProcessAsync("document.pdf", patterns);
/// </code>
/// </example>
public class DocumentProcessor
{
    /// <summary>
    /// Processes a document for redaction using specified patterns.
    /// </summary>
    /// <param name="filePath">Path to the document file</param>
    /// <param name="patterns">List of redaction patterns to apply</param>
    /// <param name="options">Processing options (optional)</param>
    /// <returns>A task representing the processing operation with results</returns>
    /// <exception cref="FileNotFoundException">
    /// Thrown when the specified file does not exist
    /// </exception>
    /// <exception cref="UnsupportedFormatException">
    /// Thrown when the file format is not supported
    /// </exception>
    public async Task<ProcessResult> ProcessAsync(
        string filePath, 
        IList<RedactionPattern> patterns,
        ProcessingOptions options = null)
    {
        // Implementation
    }
}
```

### Go

```go
// Package auth provides authentication and authorization services.
//
// This package handles user authentication, token management, and
// role-based access control for the application. It supports
// multiple authentication providers including OAuth2 and JWT.
//
// Example usage:
//
//auth := auth.NewService(config)
//token, err := auth.Authenticate(email, password)
//if err != nil {
//log.Fatal(err)
//}
package auth

// AuthService handles user authentication and authorization.
type AuthService struct {
config *Config
cache  Cache
}

// Authenticate validates user credentials and returns a token.
//
// The function performs the following steps:
//   1. Validates email format and password strength
//   2. Checks credentials against the user database
//   3. Generates and returns a JWT token
//
// Parameters:
//   - email: User's email address (must be valid format)
//   - password: User's password (must meet complexity requirements)
//
// Returns:
//   - *Token: Authentication token with user claims
//   - error: Authentication error if credentials are invalid
//
// Example:
//
//token, err := service.Authenticate("user@example.com", "password123")
//if err != nil {
//return fmt.Errorf("authentication failed: %w", err)
//}
func (s *AuthService) Authenticate(email, password string) (*Token, error) {
    // Implementation
}
```

### Rust

```rust
/// Document processing service for redaction operations.
/// 
/// This service provides functionality to process various document formats
/// and apply redaction patterns to protect sensitive information.
/// 
/// # Examples
/// 
/// ```
/// use redactor::DocumentProcessor;
/// use redactor::patterns::Pattern;
/// 
/// let processor = DocumentProcessor::new();
/// let patterns = vec![Pattern::SSN, Pattern::Email];
/// let result = processor.process("document.pdf", &patterns)?;
/// ```
/// 
/// # Errors
/// 
/// This function will return an error if:
/// * The file cannot be read
/// * The document format is unsupported
/// * Processing fails due to insufficient memory
pub struct DocumentProcessor {
    config: ProcessorConfig,
}

impl DocumentProcessor {
    /// Processes a document with the specified redaction patterns.
    /// 
    /// # Arguments
    /// 
    /// * `file_path` - Path to the document file
    /// * `patterns` - Slice of redaction patterns to apply
    /// 
    /// # Returns
    /// 
    /// Returns `Ok(ProcessResult)` on success, or `Err(ProcessError)` if
    /// processing fails.
    /// 
    /// # Examples
    /// 
    /// ```
    /// let result = processor.process("doc.pdf", &[Pattern::SSN])?;
    /// println!("Redacted {} items", result.redaction_count);
    /// ```
    pub fn process(&self, file_path: &str, patterns: &[Pattern]) -> Result<ProcessResult, ProcessError> {
        // Implementation
    }
}
```

## Framework-Specific Documentation

### React Components (PropTypes/TypeScript)

```jsx
/**
 * UserProfile component displays user information with edit capabilities.
 * 
 * @component
 * @example
 * <UserProfile 
 *   user={userData} 
 *   onSave={handleSave}
 *   readonly={false} 
 * />
 */
const UserProfile = ({
  /** User data object containing profile information */
  user: {
    id: string;
    name: string;
    email: string;
    avatar?: string;
  },
  /** Callback fired when user saves profile changes */
  onSave: (userData: User) => void;
  /** Whether the profile should be read-only */
  readonly = false;
  /** Additional CSS classes to apply */
  className?: string;
}) => {
  // Component implementation
};
```

### Vue Components

```js
<template>
  <!-- Component template -->
</template>

<script>
/**
 * UserProfile component for displaying and editing user information.
 * 
 * @displayName User Profile
 * @example
 * <UserProfile :user="currentUser" @save="handleSave" />
 */
export default {
  name: 'UserProfile',
  props: {
    /**
     * User object containing profile data
     * @type {Object}
     * @required
     * @example { id: 1, name: 'John Doe', email: 'john@example.com' }
     */
    user: {
      type: Object,
      required: true,
      validator: (user) => user.id && user.name && user.email
    },
    /**
     * Whether the profile is in read-only mode
     * @type {Boolean}
     * @default false
     */
    readonly: {
      type: Boolean,
      default: false
    }
  },
  /**
   * Component emits save event when user saves changes
   * @event save
   * @type {Object} Updated user data
   */
  emits: ['save'],
  // Component implementation
}
</script>
```

## API Documentation Examples

### REST API

```yaml
# OpenAPI/Swagger format
paths:
  /api/users/{id}:
    get:
      summary: Retrieve user by ID
      description: |
        Returns detailed user information including profile data,
        preferences, and access permissions. Requires authentication
        and appropriate access rights.
      parameters:
        - name: id
          in: path
          required: true
          description: Unique user identifier
          schema:
            type: integer
            format: int64
            example: 12345
        - name: include
          in: query
          description: Additional data to include in response
          schema:
            type: array
            items:
              type: string
              enum: [preferences, permissions, activity]
      responses:
        200:
          description: User data retrieved successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/User'
        404:
          description: User not found
        403:
          description: Insufficient permissions
```

### GraphQL

```graphql
"""
User type representing a system user with profile information.

Users can have different roles and permissions within the system.
This type includes both public and private fields depending on
the requesting user's access level.
"""
type User {
  """Unique identifier for the user"""
  id: ID!
  
  """User's display name"""
  name: String!
  
  """
  User's email address
  
  Only visible to the user themselves or administrators
  """
  email: String! @auth(requires: OWNER_OR_ADMIN)
  
  """Profile avatar URL"""
  avatar: String
  
  """Date when the user was created"""
  createdAt: DateTime!
}

"""
Retrieve user information by ID
"""
query getUser(
  """User ID to retrieve"""
  $id: ID!
  
  """Additional data to include"""
  $include: [UserInclude!]
): User
```

## Documentation Tools Integration

### Generate Documentation

```bash
# Python: Generate Sphinx docs
sphinx-apidoc -o docs/ src/

# JavaScript: Generate JSDoc
jsdoc src/ -r -d docs/

# Java: Generate JavaDoc
javadoc -d docs src/**/*.java

# C#: Generate DocFX
docfx build docfx.json

# Go: Generate godoc
godoc -http=:6060

# Rust: Generate rustdoc
cargo doc --open
```

## Maintenance Guidelines

### Documentation Reviews

- **Include in Code Reviews**: Treat documentation as code
- **Automated Checks**: Use tools to verify documentation completeness
- **Regular Audits**: Schedule periodic documentation reviews
- **User Feedback**: Collect feedback on documentation clarity and accuracy

### Continuous Integration

```yaml
# Example CI check for documentation
- name: Check Documentation Coverage
  run: |
    # Python example
    interrogate --fail-under=80 src/
    
    # JavaScript example  
    jsdoc-coverage src/ --threshold=80
    
    # Custom script example
    ./scripts/check-docs-coverage.sh
```

This skill ensures comprehensive, maintainable documentation across any programming language, framework, or project type.
