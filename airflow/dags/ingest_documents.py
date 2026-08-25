"""Run a parameterized application ingestion in a Docker container."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

from airflow.providers.docker.operators.docker import DockerOperator
from airflow.sdk import DAG, Param, get_current_context, task

INGESTION_IMAGE = os.getenv('AIRFLOW_INGESTION_IMAGE', 'ai-tour-guide-ingestion:local')
INGESTION_NETWORK = os.getenv('AIRFLOW_INGESTION_NETWORK', 'ai-tour-guide-network')
DOCKER_URL = os.getenv('AIRFLOW_DOCKER_URL', 'unix://var/run/docker.sock')


def application_environment() -> dict[str, str]:
    """Return the environment shared by database initialization and ingestion."""
    return {
        'DB_HOST': os.getenv('AIRFLOW_APPLICATION_DB_HOST', 'database'),
        'DB_PORT': os.getenv('AIRFLOW_APPLICATION_DB_PORT', '5432'),
        'DB_NAME': os.environ['DB_NAME'],
        'DB_USER': os.environ['DB_USER'],
        'DB_PASSWORD': os.environ['DB_PASSWORD'],
        'DB_SCHEMA': os.getenv('DB_SCHEMA', 'public'),
        'EMBEDDING_DIMENSIONS': os.environ['EMBEDDING_DIMENSIONS'],
        'EMBEDDING_MODEL_NAME': os.environ['EMBEDDING_MODEL_NAME'],
        'EMBEDDING_NORMALIZE': os.getenv('EMBEDDING_NORMALIZE', 'true'),
    }


with DAG(
    dag_id='ingest_documents',
    description='Ingest source-file definitions through the application ingestion CLI.',
    start_date=datetime(2026, 1, 1, tzinfo=UTC),
    schedule=None,
    catchup=False,
    params={
        'source_files': Param(
            default=[],
            type='array',
            title='Source files',
            description=(
                'A non-empty JSON array with the same document definitions accepted '
                'by source_files.json.'
            ),
            minItems=1,
            items={'type': 'object'},
        ),
        'force_reingestion': Param(
            default=False,
            type='boolean',
            title='Force re-ingestion',
            description=(
                'Replace existing documents and their chunks instead of skipping them.'
            ),
        ),
    },
    tags=['ingestion', 'rag'],
) as dag:
    initialize_database = DockerOperator(
        task_id='initialize_database',
        image=INGESTION_IMAGE,
        docker_url=DOCKER_URL,
        network_mode=INGESTION_NETWORK,
        command=[
            'sh',
            '-ec',
            (
                'python -m ai_tour_guide.knowledge_base.database.init '
                '--schema "$DB_SCHEMA"'
            ),
        ],
        private_environment=application_environment(),
        api_version='auto',
        auto_remove='success',
        force_pull=False,
        mount_tmp_dir=False,
        do_xcom_push=False,
        retries=3,
        retry_delay=timedelta(minutes=1),
    )

    @task
    def source_file_environments() -> list[dict[str, str]]:
        """Convert the submitted source definitions into mapped task environments."""
        context = get_current_context()
        dag_run = context['dag_run']
        configuration = dag_run.conf if dag_run is not None else {}
        source_files = configuration.get(
            'source_files', context['params']['source_files']
        )
        force_reingestion = configuration.get(
            'force_reingestion', context['params']['force_reingestion']
        )

        if not isinstance(source_files, list) or not source_files:
            raise ValueError('source_files must be a non-empty JSON array')
        if not all(isinstance(source_file, dict) for source_file in source_files):
            raise ValueError('each source_files entry must be a JSON object')

        return [
            {
                'FORCE_REINGESTION': str(force_reingestion).lower(),
                'SOURCE_FILE_JSON': json.dumps(source_file),
            }
            for source_file in source_files
        ]

    source_file_environment_task = source_file_environments()

    DockerOperator.partial(
        task_id='run_ingestion',
        image=INGESTION_IMAGE,
        docker_url=DOCKER_URL,
        network_mode=INGESTION_NETWORK,
        command=[
            'sh',
            '-ec',
            (
                'printf "%s" "$SOURCE_FILE_JSON" '
                '| python -m ai_tour_guide.ingestion.cli run '
                '"$(if [ "$FORCE_REINGESTION" = true ]; then '
                'printf %s --force; else printf %s --skip-existing; fi)" -'
            ),
        ],
        private_environment=application_environment(),
        api_version='auto',
        auto_remove='success',
        force_pull=False,
        mount_tmp_dir=False,
        do_xcom_push=False,
    ).expand(environment=source_file_environment_task)

    initialize_database >> source_file_environment_task
