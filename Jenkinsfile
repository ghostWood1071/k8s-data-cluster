pipeline {
    agent any

    stages {
        stage('Apply namespaces') {
            when {
                changeset "k8s-data-services/namespaces.yaml"
            }
            steps {
                echo 'Start apply namespace changes'
                script {
                    sh 'kubectl apply -f k8s-data-services/namespaces.yaml'
                }
            }
        }
    }
}