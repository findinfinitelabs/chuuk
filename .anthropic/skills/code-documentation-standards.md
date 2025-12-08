# Code Documentation Standards Skill

## Core Principle

**ALWAYS maintain up-to-date documentation when creating or modifying code. Documentation must be updated simultaneously with code changes.**

## Documentation Requirements

### 1. Page/Template Documentation

- **Template Purpose**: Document what the page does and its role in the application
- **Template Variables**: List all variables passed from backend routes
- **Form Elements**: Document form fields, validation rules, and submission behavior
- **Page Dependencies**: List required CSS files, JavaScript files, and external libraries

### 2. Class Documentation

- **Class Purpose**: Explain what the class represents and its responsibilities
- **Properties**: Document all class properties with types and descriptions
- **Methods**: Document all methods with parameters, return types, and behavior
- **Usage Examples**: Provide code examples showing how to use the class

### 3. Function/Method Documentation

- **Purpose**: Clearly explain what the function does
- **Parameters**: List all parameters with types and descriptions
- **Return Value**: Document return type and what it represents
- **Side Effects**: Note any side effects or state changes
- **Error Conditions**: Document potential exceptions or error cases

### 4. CSS Documentation

- **Class Purpose**: Explain what each CSS class is for
- **Usage Context**: Where and when the class should be applied
- **Dependencies**: Note any required parent classes or Bootstrap dependencies
- **Responsive Behavior**: Document mobile/tablet adaptations

## Documentation Formats

### Python Functions/Classes

```python
def process_document(file_path: str, patterns: List[str]) -> ProcessResult:
    """
    Process a document for redaction using specified patterns.
    
    Args:
        file_path (str): Path to the document file to process
        patterns (List[str]): List of redaction patterns to apply
        
    Returns:
        ProcessResult: Object containing processed document and metadata
        
    Raises:
        FileNotFoundError: If the document file doesn't exist
        ValidationError: If patterns are invalid
        
    Example:
        result = process_document('/path/to/doc.pdf', ['ssn', 'email'])
    """
```

### HTML Template Documentation

```html
<!--
Template: signup.html
Purpose: User registration form with plan selection
Variables:
  - plan (str): Selected pricing plan (individual/corporate/enterprise)
  - request.form (dict): Form data for validation errors
Dependencies:
  - /static/css/styles.css (signup page styles)
  - Bootstrap 5.3.0
Form Submission: POST /signup
-->
```

### CSS Class Documentation

```css
/* 
Signup Card Component
Purpose: Main container for signup form with gradient background
Usage: Applied to signup form container div
Dependencies: Bootstrap container classes
Responsive: Adapts to mobile with reduced padding
*/
.signup-card {
    background: white;
    border-radius: 20px;
    /* ... */
}
```

### JavaScript Function Documentation

```javascript
/**
 * Validates signup form data before submission
 * @param {HTMLFormElement} form - The signup form element
 * @param {Object} options - Validation options
 * @param {boolean} options.checkPasswords - Whether to validate password match
 * @returns {boolean} True if form is valid, false otherwise
 * @throws {Error} If form element is not found
 */
function validateSignupForm(form, options = {}) {
    // Implementation
}
```

## When to Update Documentation

### Always Update When

1. **Creating new files** - Add comprehensive header documentation
2. **Adding new functions/methods** - Document immediately upon creation
3. **Modifying existing functions** - Update documentation to match changes
4. **Changing parameters** - Update parameter documentation
5. **Adding CSS classes** - Document purpose and usage
6. **Creating templates** - Document variables, forms, and dependencies

### Documentation Locations

- **Inline Comments**: For complex logic and implementation details
- **Docstrings**: For functions, classes, and modules
- **Header Comments**: For templates and major file sections
- **README Files**: For major components or subsystems
- **API Documentation**: For public interfaces and endpoints

## Documentation Standards

- **Be Concise**: Clear and to the point
- **Be Complete**: Cover all parameters, returns, and exceptions
- **Be Current**: Update immediately when code changes
- **Be Consistent**: Follow established patterns and formats
- **Include Examples**: Show typical usage patterns
- **Document Edge Cases**: Note unusual behavior or limitations

## Enforcement

- **Never commit code without documentation**
- **Review documentation during code reviews**
- **Update related documentation when modifying dependencies**
- **Maintain documentation coverage as code coverage metric**

This skill ensures that all code remains maintainable and understandable by keeping documentation synchronized with implementation changes.
