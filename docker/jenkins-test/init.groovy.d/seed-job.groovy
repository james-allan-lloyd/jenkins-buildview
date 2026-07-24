import jenkins.model.Jenkins
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition

def jenkins = Jenkins.get()

// Multiple jobs so the job-browser list has more than one entry -- useful
// for exercising list navigation (e.g. up/down between entries) manually.
def seedJobs = [
    "parallel-nested-demo": "/usr/share/jenkins/ref/pipelines/Jenkinsfile.demo",
    "simple-demo"         : "/usr/share/jenkins/ref/pipelines/Jenkinsfile.simple",
]

seedJobs.each { jobName, pipelinePath ->
    if (jenkins.getItem(jobName) == null) {
        def job = jenkins.createProject(WorkflowJob, jobName)
        def pipelineScript = new File(pipelinePath).text
        job.setDefinition(new CpsFlowDefinition(pipelineScript, true))
        job.save()
        println "Created seed job: ${jobName}"
    } else {
        println "Seed job already exists: ${jobName}"
    }
}
jenkins.save()
