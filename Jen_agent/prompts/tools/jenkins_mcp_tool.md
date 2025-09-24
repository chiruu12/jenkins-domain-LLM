### Jenkins Live Interaction Tool

This tool provides a direct, live interface to a Jenkins instance to perform actions and retrieve real-time information. Use it when you need to check the current status of jobs, trigger new builds, or inspect live configurations, which is not possible with static log or workspace files.

**Function Signature:**
`execute_jenkins_command(instructions: str) -> str`

**Core Capabilities:**
- **Job Management:** Get details for a specific job or a list of jobs. Trigger new builds, including parameterized builds (e.g., specifying a branch).
- **Build Information:** Retrieve the status, logs, or SCM changes for a specific build or the most recent build of a job.
- **System Health:** Check the overall status of the Jenkins instance or identify the current user.

**How to Use:**
Formulate your `instructions` as a clear, direct command to a Jenkins expert. Be specific about job names and the information you require.

**Example Usage:**
To get the logs from the latest build of a job named 'deploy-to-prod', you would call the tool like this:
`execute_jenkins_command(instructions="Get the build log for the last build of the 'deploy-to-prod' job")`