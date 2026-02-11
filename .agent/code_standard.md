---
inclusion: always
---

# Code Standards

## Code Style

- Format all TypeScript, JavaScript, and JSX files with **Prettier** using the settings from `.prettierrc` (2-space indentation, single quotes, trailing commas, 80 character line width)
- Follow the ESLint rules defined in `.eslintrc.json`
- **No `console.log` statements**. Use logger utilities when debugging
- Avoid `var`; use `const` or `let`. Unused variables prefixed with `_` are allowed
- The repository uses TypeScript; prefer TypeScript for new files
- Import specific methods from lodash instead of the entire library
- Use strict equality (`===`) instead of loose equality (`==`)

## DRY Principles (CRITICAL)

- **NEVER duplicate code** - always extract common patterns into reusable functions
- **NEVER repeat similar logic** - create configuration-driven solutions instead
- **NEVER copy-paste code blocks** - refactor into shared utilities or services
- **ALWAYS question repetition** - if you see similar code twice, refactor immediately
- **ALWAYS use reusable components** - leverage `/packages/components` for shared UI elements
- **ALWAYS use shared utilities** - leverage `/packages/utils` and `/packages/helpers` for common logic
- **ALWAYS use shared hooks** - leverage `/packages/hooks` for reusable React logic
- **USE configuration arrays** instead of multiple similar functions
- **CREATE generic handlers** that work with different data types
- **EXTRACT common patterns** into utility functions or base classes
- **REFACTOR before adding** - if you need something similar to existing code, refactor to make it reusable first
- **This rule has zero exceptions** - any duplicated code will be rejected

## Component Reusability Requirements

- Before creating a new component, check if a similar one exists in `/packages/components`
- If a component will be used in more than one place, it MUST be in `/packages/components`
- Application-specific components stay in the app; shared components MUST be extracted to packages
- All shared components must be properly typed, documented, and tested
- Components must be composable and accept standard props (`className`, `children`, etc.)

## TypeScript Standards

- **Use STRICT TypeScript typing** - NO `any` types allowed
- **Define proper interfaces** for all parameters and return values
- **Follow DRY principles** - extract common patterns
- Prefer `const` or `let` over `var`
- Unused variables prefixed with `_` are allowed

## Performance & Efficiency Standards

- **Time Complexity**: Aim for O(1) constant time operations where possible, O(log n) for searches, avoid O(n²) nested loops
- **Space Complexity**: Minimize memory usage, use efficient data structures (Map/Set over arrays for lookups)
- **Algorithm Efficiency**: Choose optimal algorithms for data processing and manipulation
- **Early Returns**: Use early returns to avoid unnecessary processing
- **Lazy Evaluation**: Implement lazy loading and evaluation where appropriate
- **Memoization**: Cache expensive calculations and API responses
- **Debouncing**: Use debouncing for user input and API calls

## Code Documentation Standards

- **JSDoc Requirements**: Add JSDoc comments for all public functions, classes, and interfaces
- **Function Documentation**: Document parameters, return values, and time/space complexity
- **Complex Logic**: Add inline comments for non-obvious business logic
- **API Documentation**: Document all API endpoints and data structures
- **Component Documentation**: Document component props, usage examples, and accessibility features
- **Performance Notes**: Document performance considerations and optimization decisions

## Complexity Documentation Requirements

- **Time Complexity**: Document Big O notation for all algorithms
- **Space Complexity**: Document memory usage patterns
- **Performance Characteristics**: Note performance under different data sizes
- **Optimization Notes**: Document why specific optimizations were chosen
- **Benchmark Results**: Include performance benchmarks for critical functions

## Naming Conventions

- **Components**: PascalCase with descriptive names (BusinessSelector, AuthGuard, RequestOutletAccessModal)
- **Files**: Use descriptive names that match component names
- **Constants**: UPPER_SNAKE_CASE in dedicated constants files
- **Package Prefixes**: Use consistent prefixes
- **Export Names**: Use consistent naming patterns in index.ts files

## Constants Management

- **Centralized Constants**: Store all constants in dedicated files (see pos-core/constants.ts)
- **Validation Messages**: Use constants for all error messages, never hardcode strings
- **Business Rules**: Define business logic constants (MAX_REFUND_DAYS, TRANSACTION_LIMITS)
- **Status Enums**: Use const assertions for status types (PAYMENT_TYPES, TRANSACTION_STATUS)
- **Receipt Text**: Centralize all receipt formatting strings

## DRY Enforcement (ZERO TOLERANCE)

- **Code Duplication Detection**: Before writing ANY code, search codebase for similar implementations
- **Three-Strike Rule**: If you see similar code 3+ times, it MUST be extracted to shared utility
- **Function Extraction**: Extract any logic used more than once into reusable functions
- **Configuration-Driven**: Use configuration objects instead of multiple similar functions
- **Generic Solutions**: Write generic, parameterized solutions instead of specific implementations
- **Shared Constants**: Never duplicate string literals, numbers, or configuration values
- **Component Abstraction**: Abstract common UI patterns into reusable components
- **Hook Extraction**: Extract stateful logic into custom hooks for reuse

## Component Naming Standards

- **Descriptive Names**: Use clear, descriptive names that indicate component purpose
- **Consistent Patterns**: Follow established naming patterns across the codebase

## Component Standards

- **HiringCafe Prefix**: All components use 'HiringCafe' prefix for consistency
- **Props Interface**: Always define TypeScript interfaces for component props
- **Default Exports**: Use default exports for components, named exports for utilities
- **Composition**: Design components to be composable and reusable
- **Accessibility**: Include proper ARIA labels and keyboard navigation
- **Performance**: Implement React.memo for expensive components
- **Error Boundaries**: Wrap complex components with error boundaries
- **LINES OF CODE PER FILE**: No file should exceed 350 lines of code

## Change Scope Limits

- Number of files changed should not be more than 10

## Code Quality Requirements

- All code must be concise, readable, performant, efficient, scalable, and maintainable
- Ensure existing functions, hooks, and utilities are used before adding new ones to avoid repetition
- Follow DRY principles at all times
- Use separation of concerns for modules, services, and components
- Modularize where possible and create reusable components when future use is likely
- Avoid prop drilling; prefer context, hooks, or state management patterns
- Follow system design tokens, design systems, and product requirements
