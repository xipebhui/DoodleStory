# Java Development Standard

## Purpose

Use this standard when adding or changing Java code. Keep Java code conventional, readable, testable, and compatible with the project's selected JDK and build tool.

## Source Baseline

- [Google Java Style Guide](https://google.github.io/styleguide/javaguide.html)
- [Oracle Java Code Conventions](https://www.oracle.com/java/technologies/javase/codeconventions-contents.html)
- [Java SE Specifications](https://docs.oracle.com/javase/specs/)
- [JUnit 5 User Guide](https://junit.org/junit5/docs/current/user-guide/)

## Rules

1. Use Google Java Style as the default style guide for new Java code unless the repository already enforces another formatter.
2. Treat Oracle's code conventions as background reference, not the primary formatter rule, because modern Java teams more commonly automate formatting through current tools.
3. Keep package names lowercase and aligned to the project domain.
4. Prefer clear class boundaries over deep inheritance. Use interfaces for real substitution points, not speculative abstraction.
5. Keep constructors lightweight and avoid hidden I/O or network work during object construction.
6. Make nullability and optional values explicit through types, validation, or documented contracts.
7. Do not catch broad exceptions unless the handler can add context, recover intentionally, or translate to a meaningful boundary error.
8. Use JUnit 5 for new tests unless the project has already standardized on another test framework.
9. Keep build configuration minimal. Add Maven or Gradle plugins only when they are needed for compilation, testing, packaging, or verified quality gates.

## Expected Project Shape

- Maven projects should keep production code under `src/main/java` and tests under `src/test/java`.
- Gradle projects should follow the same source set convention unless the existing build defines another layout.
- Spring or framework-specific code should keep domain logic separate from controllers, configuration, and persistence adapters.

## Verification

When Java code exists, `./scripts/check.sh` should eventually delegate to the selected build tool, such as:

```bash
mvn test
```

or:

```bash
./gradlew test
```

Do not add both Maven and Gradle unless the project explicitly needs both.
