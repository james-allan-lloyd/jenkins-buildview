import jenkins.model.Jenkins
import org.jenkinsci.plugins.workflow.job.WorkflowJob
import org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition

def jenkins = Jenkins.get()
def jobName = "parallel-nested-demo"

if (jenkins.getItem(jobName) == null) {
    def job = jenkins.createProject(WorkflowJob, jobName)
    def pipelineScript = new File("/usr/share/jenkins/ref/pipelines/Jenkinsfile.demo").text
    job.setDefinition(new CpsFlowDefinition(pipelineScript, true))
    job.save()
    jenkins.save()
    println "Created seed job: ${jobName}"
} else {
    println "Seed job already exists: ${jobName}"
}
