````markdown
---
name: approval-based-implementation
description: Structured problem-solving workflow requiring investigation, proposal, and explicit approval before implementing changes. Use when user reports issues, asks for improvements, or requests features. Always present proposed changes and get approval before executing.
---

# Approval-Based Implementation

> ## ⚠️ Repo Reality Check (read this first)
>
> The default agent posture in this workspace is **"implement, don't just suggest"** (see the project standing instructions). This skill describes an **opt-in** workflow for situations where a proposal+approval gate is genuinely useful.
>
> **Use this skill when:**
> - The change is broadly destructive or hard to reverse (DB migration, force-push, dropping tables, deleting users).
> - The change touches shared infrastructure or production secrets.
> - The user has explicitly asked you to plan first.
> - The change spans many files and you're uncertain about scope.
>
> **Do NOT use this skill when:**
> - The change is local, reversible, and the intent is clear (the default — just do it).
> - You're answering a question or doing read-only research.
>
> The `manage_todo_list` tool referenced below **is** available in this VS Code agent environment. Use it for multi-step work; skip it for single-step tasks.

## Core Principle (when this skill applies)

**Present a detailed proposal and receive explicit approval before executing irreversible or high-risk changes.**

## Workflow Steps

### 1. Investigation Phase

When a user reports an issue or requests a change:

1. **Acknowledge the request** - Confirm understanding of the problem/request
2. **Gather context** - Read relevant files, logs, and configuration
3. **Identify root cause** - Use grep, file reading, and analysis to understand the issue
4. **Document findings** - Clearly explain what you discovered

### 2. Proposal Phase

After investigation, present a comprehensive proposal:

```markdown
## Investigation Summary
[What you found - root cause, current behavior, etc.]

## Proposed Solution
[High-level approach to fix the issue]

## Changes Required
1. **File: path/to/file.py**
   - What will be changed and why
   - Show code snippet of what will be added/modified
   
2. **File: path/to/another.py**
   - What will be changed and why
   - Show code snippet of what will be added/modified

## Expected Impact
- What will improve
- Any potential side effects
- Testing recommendations
```

### 3. Todo Creation

Create a structured todo list using `manage_todo_list`:

```javascript
{
  "todoList": [
    {
      "id": 1,
      "title": "Add caching for Cosmos DB queries",
      "status": "not-started"
    },
    {
      "id": 2,
      "title": "Update /api/database/distinct endpoint",
      "status": "not-started"
    },
    {
      "id": 3,
      "title": "Add error handling for rate limits",
      "status": "not-started"
    },
    {
      "id": 4,
      "title": "Test changes and verify fix",
      "status": "not-started"
    }
  ]
}
```

### 4. Approval Gate

**STOP and ask for approval:**

> "Would you like me to proceed with these changes? You can:
> - Approve all changes
> - Approve specific items only
> - Request modifications to the approach
> - Ask questions about the implementation"

### 5. Implementation Phase

Only after receiving approval:

1. **Mark todo as in-progress** before starting each item
2. **Implement the change** using appropriate tools
3. **Mark todo as completed** immediately after finishing
4. **Verify the change** works as expected
5. **Report completion** with summary

### 6. Verification Phase

After implementation:

1. **Test the fix** - Run relevant commands/checks
2. **Verify logs** - Check for errors or warnings
3. **Confirm resolution** - Verify original issue is resolved
4. **Document completion** - Summarize what was done

## Communication Pattern

### Investigation Report Format

```markdown
## Issue Analysis

**Problem:** [Brief description]

**Root Cause:** [What's causing the issue]

**Evidence:**
- [Log excerpt or error message]
- [Relevant code snippet]
- [Configuration issue]

## Proposed Fix

**Approach:** [How we'll solve it]

**Changes:**
1. [Specific file/line changes]
2. [Configuration updates]
3. [New code additions]

**Code Preview:**
```language
// Show actual code that will be added/changed
function example() {
  // New implementation
}
```

**Benefits:**
- [Improvement 1]
- [Improvement 2]

**Risks:**
- [Potential issue 1 and mitigation]
- [Potential issue 2 and mitigation]

**Testing Plan:**
- [How to verify it works]
- [What to check after deployment]

Would you like me to proceed with this implementation?
```

## Example Scenarios

### Scenario 1: Bug Report

**User:** "Database is returning 500 errors"

**Response:**
1. Investigate logs and identify rate limiting
2. Present proposal with caching solution
3. Show code changes for each endpoint
4. Create todo list with 4-5 specific tasks
5. Ask: "Should I implement these changes?"
6. Only after approval, execute changes one by one

### Scenario 2: Feature Request

**User:** "Add export functionality to database page"

**Response:**
1. Review current database page structure
2. Propose export button with format options
3. Show UI changes and backend endpoint code
4. Create todo list for frontend, backend, testing
5. Ask: "Does this approach work for you?"
6. Implement after approval with progress updates

### Scenario 3: Performance Issue

**User:** "Page loads slowly"

**Response:**
1. Analyze network requests and timing
2. Identify bottlenecks (e.g., multiple API calls)
3. Propose solutions (caching, batching, lazy loading)
4. Show code changes with performance metrics
5. Create todo list with benchmarking tasks
6. Ask: "Which optimization should I prioritize?"
7. Implement approved items

## Best Practices

### Investigation
- ✅ Read actual files, don't assume structure
- ✅ Check logs for real error messages
- ✅ Grep for relevant patterns
- ✅ Understand data flow and dependencies
- ❌ Don't guess at solutions
- ❌ Don't skip root cause analysis

### Proposals
- ✅ Show specific code changes, not pseudo-code
- ✅ Include file paths and line numbers
- ✅ Explain trade-offs and alternatives
- ✅ Estimate complexity (simple/medium/complex)
- ❌ Don't be vague ("we'll improve performance")
- ❌ Don't hide potential issues

### Implementation
- ✅ Update todos before and after each step
- ✅ Test incrementally
- ✅ Commit logical chunks
- ✅ Report progress clearly
- ❌ Don't batch all changes at once
- ❌ Don't move to next task without completing current
- ❌ Don't implement without approval

### Communication
- ✅ Be clear and specific
- ✅ Show, don't just tell
- ✅ Ask clarifying questions
- ✅ Provide options when multiple approaches exist
- ❌ Don't be overly verbose
- ❌ Don't assume user preferences

## Approval Variations

### Explicit Approval Phrases
- "Yes, proceed"
- "Go ahead"
- "Implement those changes"
- "That looks good, do it"
- "Approved"

### Modification Requests
- "Change X to Y instead"
- "Skip item 2, do the rest"
- "Can you also add Z?"
- "Use a different approach for..."

### Rejection/Reconsideration
- "No, let's try a different approach"
- "I don't think that will work because..."
- "Hold off on that for now"

## Todo List Management

### Creating Todos
```javascript
manage_todo_list({
  "todoList": [
    {"id": 1, "title": "Specific actionable task", "status": "not-started"},
    {"id": 2, "title": "Another specific task", "status": "not-started"}
  ]
})
```

### Updating During Work
```javascript
// Before starting task 1
manage_todo_list({
  "todoList": [
    {"id": 1, "title": "Task 1", "status": "in-progress"},
    {"id": 2, "title": "Task 2", "status": "not-started"}
  ]
})

// After completing task 1
manage_todo_list({
  "todoList": [
    {"id": 1, "title": "Task 1", "status": "completed"},
    {"id": 2, "title": "Task 2", "status": "not-started"}
  ]
})
```

## Integration with Other Skills

- **code-documentation-standards**: Update docs as part of changes
- **git-workflow-management**: Commit with meaningful messages
- **python-venv-management**: Use .venv for Python changes
- **security-environment-standards**: Review security implications
- **database-management-operations**: Follow DB best practices

## Success Criteria

A successful implementation workflow includes:

1. ✅ Clear problem identification
2. ✅ Detailed proposal with code previews
3. ✅ Structured todo list
4. ✅ Explicit approval received
5. ✅ Incremental implementation with progress updates
6. ✅ Verification that fix works
7. ✅ Summary of changes made

## Anti-Patterns to Avoid

❌ **Immediately implementing** when user reports issue
❌ **Vague proposals** without code examples
❌ **Skipping approval step** and going straight to changes
❌ **Batching all todos** as completed without doing them
❌ **Not testing** before marking complete
❌ **Moving to next task** before finishing current one
❌ **Assuming user wants** a particular solution

## Remember

> **The goal is collaborative problem-solving, not autonomous fixing. The user should always understand what you're doing and approve changes before execution.**

````
