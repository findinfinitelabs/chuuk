# External CSS Styling Standards

## Core Principle

**NEVER use inline styling or in-page `<style>` blocks in HTML templates. ALL styling must be in external CSS files.**

## Universal Rules

1. **No Inline Styles**: Never add `style="..."` attributes to HTML elements
2. **No In-Page Styling**: Never add `<style>` blocks within HTML templates  
3. **External CSS Only**: All styling must be in dedicated CSS files
4. **Framework Consistency**: Use your project's CSS framework (Bootstrap, Tailwind, etc.) as foundation
5. **Utility Classes**: Leverage existing framework utility classes when possible
6. **Maintainable Architecture**: Follow consistent CSS file organization patterns

## CSS Organization Patterns

### Standard Web Projects

```txt
/assets/css/
  ├── main.css          - Core application styles
  ├── components.css    - Reusable UI components
  ├── pages.css         - Page-specific styles
  ├── theme.css         - Theme variables and overrides
  └── vendor.css        - Third-party customizations
```

### Framework-Specific Examples

#### Django/Flask Projects

```txt
/static/css/
  ├── base.css
  ├── components.css
  └── custom.css
```

#### React/Vue Projects

```txt
/src/styles/
  ├── globals.css
  ├── components/
  └── pages/
```

#### Rails Projects

```txt
/app/assets/stylesheets/
  ├── application.css
  ├── components/
  └── pages/
```

## CSS Framework Integration

### Bootstrap Projects

```css
/* Use Bootstrap utilities first */
.card-custom {
  @extend .card;
  /* Custom additions only */
  box-shadow: var(--bs-box-shadow-lg);
}
```

### Tailwind CSS Projects

```css
/* Prefer utility classes, extract components when needed */
@layer components {
  .btn-custom {
    @apply px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600;
  }
}
```

### Custom CSS Projects

```css
/* Establish design system variables */
:root {
  --primary-color: #007bff;
  --secondary-color: #6c757d;
  --border-radius: 0.375rem;
}
```

## Best Practices

### Class Naming Conventions

- **BEM Methodology**: `.block__element--modifier`
- **Semantic Names**: `.navigation-header` not `.blue-box`
- **Component-Based**: `.card-user`, `.form-login`, `.button-primary`

### CSS Organization

```css
/* Component: User Profile Card */
.profile-card {
  /* Layout */
  display: flex;
  flex-direction: column;
  
  /* Visual */
  background: var(--card-bg);
  border-radius: var(--border-radius);
  box-shadow: var(--shadow-md);
  
  /* Spacing */
  padding: 1.5rem;
  margin-bottom: 1rem;
}

.profile-card__header {
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 1rem;
  margin-bottom: 1rem;
}

.profile-card__avatar {
  width: 4rem;
  height: 4rem;
  border-radius: 50%;
}
```

## Examples by Technology Stack

### React Components

```jsx
// ❌ WRONG
function UserCard() {
  return (
    <div style={{background: 'white', padding: '20px'}}>
      Content
    </div>
  );
}

// ✅ CORRECT
function UserCard() {
  return (
    <div className="user-card">
      Content
    </div>
  );
}
```

### Vue Components

```vue
<!-- ❌ WRONG -->
<template>
  <div style="background: white; padding: 20px;">
    Content
  </div>
</template>

<!-- ✅ CORRECT -->
<template>
  <div class="user-card">
    Content
  </div>
</template>

<style scoped>
.user-card {
  background: white;
  padding: 1.25rem;
}
</style>
```

### Django Templates

```html
<!-- ❌ WRONG -->
<div style="background: white; padding: 20px;">
  Content
</div>

<!-- ✅ CORRECT -->
<div class="user-card">
  Content
</div>
```

## Multi-Language Support

### CSS Variables for Theming

```css
:root {
  --text-direction: ltr;
  --text-align-start: left;
  --text-align-end: right;
}

[dir="rtl"] {
  --text-direction: rtl;
  --text-align-start: right;
  --text-align-end: left;
}

.content {
  direction: var(--text-direction);
  text-align: var(--text-align-start);
}
```

## Framework-Specific Patterns

### Next.js with CSS Modules

```jsx
import styles from './UserCard.module.css';

export default function UserCard() {
  return (
    <div className={styles.card}>
      Content
    </div>
  );
}
```

### Angular with Component Styles

```typescript
@Component({
  selector: 'app-user-card',
  template: '<div class="user-card">Content</div>',
  styleUrls: ['./user-card.component.css']
})
```

### Svelte with Scoped Styles

```svelte
<div class="user-card">
  Content
</div>

<style>
  .user-card {
    background: white;
    padding: 1.25rem;
  }
</style>
```

## Enforcement Guidelines

- **Code Review Checklist**: Check for inline styles in all PRs
- **Linting Rules**: Configure ESLint/Stylelint to flag inline styles
- **Build Process**: Fail builds that contain inline styling
- **Documentation**: Maintain CSS architecture documentation
- **Team Standards**: Establish and communicate CSS conventions

This skill ensures consistent, maintainable styling architecture across any web development project, regardless of framework or technology stack.
