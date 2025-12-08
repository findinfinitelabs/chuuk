# CSS Styling Standards Skill

## Core Principle

**NEVER use inline styling or in-page `<style>` blocks in HTML templates. ALL styling must be in external CSS files.**

## Rules

1. **No Inline Styles**: Never add `style="..."` attributes to HTML elements
2. **No In-Page Styling**: Never add `<style>` blocks within HTML templates
3. **External CSS Only**: All styling must be in dedicated CSS files in `/web/static/css/`
4. **Bootswatch Reference**: Use Bootswatch themes as the foundation for styling
5. **Bootstrap Classes**: Leverage existing Bootstrap utility classes when possible
6. **Consistent Architecture**: Follow the existing CSS file organization
7. **Avoid !important**: Use specific selectors instead of `!important` flags to prevent specificity issues

## CSS File Locations

- `/web/static/css/styles.css` - Main application styles
- `/web/static/css/theme.css` - Theme-specific overrides
- `/web/static/css/components.css` - Reusable component styles
- `/web/static/css/admin.css` - Admin-specific styles
- `/web/static/css/integrations.css` - Integration-specific styles

## When Making Style Changes

1. **Identify the appropriate CSS file** based on the component/page type
2. **Add or modify CSS classes** in the external file
3. **Apply classes to HTML elements** using the `class` attribute
4. **Never create template-specific styling** - make it reusable

## Example - WRONG

```html
<div style="background: red; padding: 10px;">Content</div>
<style>
.my-custom-class { color: blue; }
</style>
```

```css
/* Using !important flags - creates specificity issues */
.form-input {
    width: 100% !important;
    height: 2rem !important;
}
```

## Example - CORRECT

In `/web/static/css/styles.css`:

```css
.alert-custom {
    background: var(--danger-color);
    padding: 0.625rem;
    color: var(--text-light);
}

/* Use specific selectors instead of !important */
.form-container .form-input,
.signup-card .form-input {
    width: 100%;
    height: 2rem;
}
```

In HTML template:

```html
<div class="alert-custom">Content</div>
```

## Enforcement

- **Always check templates** for inline styles or `<style>` blocks
- **Remove any existing inline styling** and move to appropriate CSS files
- **Use semantic, reusable class names** that follow the existing naming conventions
- **Leverage CSS variables** defined in theme.css for consistency
- **Avoid !important flags** - use specific selectors to achieve proper specificity
- **Test CSS specificity** - ensure styles can be overridden without !important

This skill ensures consistent, maintainable styling architecture across the application.
