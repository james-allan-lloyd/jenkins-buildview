FROM jenkins/jenkins:lts-jdk17

ENV CASC_JENKINS_CONFIG=/usr/share/jenkins/ref/casc_configs
ENV JENKINS_OPTS="--httpPort=8080"

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

COPY casc_configs /usr/share/jenkins/ref/casc_configs
COPY init.groovy.d /usr/share/jenkins/ref/init.groovy.d
COPY pipelines /usr/share/jenkins/ref/pipelines
