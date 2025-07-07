### Root Cause
The build failed due to a syntax error in the `Jenkinsfile`, specifically an unexpected token at the start of the file.

### Evidence
*   **[Syntax Error Message]:** The error message points out a specific issue with the Groovy syntax used in the `Jenkinsfile`.

    ```
    org.codehaus.groovy.control.MultipleCompilationErrorsException: startup failed:
    WorkflowScript: 1: unexpected token: < @ line 1, column 54.
       eddableBadgeConfiguration(id: <'my-id',
                                   ^
    1 error
    ```

### Suggested Fix
1. Open your `Jenkinsfile` and locate the syntax issue indicated by the error message.
2. Correct the following line that contains the unwanted token `<'my-id'`: `eddableBadgeConfiguration(id: <'my-id',` to `eddableBadgeConfiguration(id: 'my-id',`.

#### Example Fix
```groovy
// Corrected line in Jenkinsfile
eddableBadgeConfiguration(id: 'my-id',
```
This should resolve the syntax error and allow the pipeline to compile successfully.

