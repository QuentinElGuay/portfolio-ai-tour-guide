## Ingestion

You can either run the **ingestion** process using Airflow or the docker CLI.

### Airflow

To run the ingestion using Airflow, start the Airflow environment by running the
command:

```bash
$ make airflow
```

to set up Airflow, the ingestion service and the database. Wait for Docker to create all
the services for the ingestion. This might take a few minutes:

```bash
 ✔ Image ai-tour-guide-airflow:local                 Built                                                                               16.0s
 ✔ Image ai-tour-guide-base:local                    Built                                                                               16.0s
 ✔ Image ai-tour-guide-ingestion:local               Built                                                                               16.0s
 ✔ Network ai-tour-guide_default                     Created                                                                              0.4s
 ✔ Container ai-tour-guide-database-1                Healthy                                                                             72.3s
 ✔ Container ai-tour-guide-airflow-database-1        Exited                                                                              72.3s
 ✔ Container ai-tour-guide-airflow-ingestion-image-1 Exited                                                                              72.3s
 ✔ Container ai-tour-guide-airflow-init-1            Exited                                                                              71.9s
 ✔ Container ai-tour-guide-airflow-webserver-1       Healthy                                                                            142.8s
 ✔ Container ai-tour-guide-airflow-scheduler-1       Healthy                                                                             71.4s
 ✔ Container ai-tour-guide-airflow-dag-processor-1   Healthy                                                                       39.6s
```

Once the `airflow-webserver` is ready, open the Airflow interface at
[http://localhost:8080/](http://localhost:8080/) and sign in. The credentials are
defined in your `.env` file. By default, the credentials are:

```
Username: admin
Password: pa$$word123
```

![Airflow sign in screen](images/00_airflow_sign_in.png "Airflow sign in screen")

Open the `Dags` tab and click on the `Trigger` button of the `ingest_documents` DAG:
![DAGs screen](images/01_airflow_dags.png "Click on 'Trigger the DAG'")

Copy the content of the `source_files.json` file into the `Source files` fields and
click on `Trigger`. If you want to overwrite a previous ingestion, select the
`Force the re-ingestion` option.
![Trigger DAG screen](images/02_airflow_trigger_dag.png "Set the DAG parameters")

Wait for the DAG run to finish. This might take a few minutes.
![All the tasks are marked as success](images/03_airflow_dag_run.png "Successful DAG")
