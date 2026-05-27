"""
Celery tasks for Behavioral Risk Scoring pipeline orchestration.
"""
import logging
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import current_app, has_app_context

from app.tasks import celery_app

logger = logging.getLogger(__name__)

TOPIC_TRAINING_LOCK = "/app/models/.topic_model_training.lock"


def _run_with_app_context(fn):
    if has_app_context():
        return fn()

    from app import create_app

    app = create_app(os.getenv("FLASK_ENV", "production"))
    with app.app_context():
        return fn()


@celery_app.task(bind=True, name="pipeline.process_nlp")
def process_nlp_task(self):
    def _run():
        from app.services.pipeline_service import PipelineService

        self.update_state(state="PROGRESS", meta={"progress": 10, "step": "process_nlp"})
        result = PipelineService().process_nlp()
        self.update_state(state="PROGRESS", meta={"progress": 100, "step": "process_nlp"})
        return result

    return _run_with_app_context(_run)


@celery_app.task(bind=True, name="pipeline.generate_features")
def generate_features_task(self):
    def _run():
        from app.services.pipeline_service import PipelineService

        self.update_state(state="PROGRESS", meta={"progress": 10, "step": "generate_features"})
        result = PipelineService().generate_features()
        self.update_state(state="PROGRESS", meta={"progress": 100, "step": "generate_features"})
        return result

    return _run_with_app_context(_run)


@celery_app.task(bind=True, name="pipeline.train_topic_model")
def train_topic_model_task(
    self,
    overwrite: bool = True,
    replace_topics: bool = True,
    source: str = "db",
    csv_path: str = None,
    min_chars: int = 15,
    min_docs: int = 50,
    target_topics: int = 30,
):
    def _run():
        lock_path = Path(TOPIC_TRAINING_LOCK)
        lock_fd = None
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, self.request.id.encode("utf-8"))
        except FileExistsError as exc:
            raise RuntimeError("Training topic model sedang berjalan. Tunggu task aktif selesai sebelum menjalankan lagi.") from exc

        self.update_state(state="PROGRESS", meta={"progress": 5, "step": "train_topic_model"})

        try:
            version = f"bertopic_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            cmd = [
                sys.executable,
                "-m",
                "scripts.train_topic_model",
                "--source",
                source or "db",
                "--min-chars",
                str(min_chars),
                "--min-docs",
                str(min_docs),
                "--model-version",
                version,
                "--target-topics",
                str(target_topics),
            ]
            if overwrite:
                cmd.append("--overwrite")
            if replace_topics:
                cmd.append("--replace-topics")
            if csv_path:
                cmd.extend(["--csv-path", csv_path])

            logger.info("Starting topic model training task: %s", " ".join(cmd))
            self.update_state(state="PROGRESS", meta={"progress": 20, "step": "train_topic_model"})

            completed = subprocess.run(
                cmd,
                cwd=os.getcwd(),
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )

            if completed.returncode != 0:
                logger.error("Topic model training failed: %s", completed.stderr)
                raise RuntimeError(completed.stderr[-3000:] or "Train topic model failed")

            self.update_state(state="PROGRESS", meta={"progress": 100, "step": "train_topic_model"})
            return {
                "success": True,
                "status": "completed",
                "model_version": version,
                "topic_model_path": os.getenv("TOPIC_MODEL_PATH", "/app/models/topic_model"),
                "stdout": completed.stdout[-3000:],
            }
        finally:
            if lock_fd is not None:
                os.close(lock_fd)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    return _run_with_app_context(_run)


@celery_app.task(bind=True, name="pipeline.run_scoring")
def run_scoring_task(self):
    def _run():
        from app.services.pipeline_service import PipelineService

        self.update_state(state="PROGRESS", meta={"progress": 10, "step": "run_scoring"})
        result = PipelineService().run_scoring()
        self.update_state(state="PROGRESS", meta={"progress": 100, "step": "run_scoring"})
        return result

    return _run_with_app_context(_run)


@celery_app.task(bind=True, name="pipeline.retrain_model")
def retrain_model_task(self, cutoff_date: str = None, churn_window: int = 90, observation_window: int = 90):
    """
    Research/admin-only retraining task.

    This calls the existing training script and returns real output. If the
    script cannot train because data/labels are insufficient, the task fails
    with that error instead of producing placeholder metrics.
    """
    def _run():
        self.update_state(state="PROGRESS", meta={"progress": 5, "step": "retrain_model"})

        version = datetime.utcnow().strftime("v%Y%m%d_%H%M%S")
        cmd = [
            sys.executable,
            "-m",
            "scripts.train_model",
            "--churn-window",
            str(churn_window),
            "--observation-window",
            str(observation_window),
            "--version",
            version,
        ]
        if cutoff_date:
            cmd.extend(["--cutoff-date", cutoff_date])

        logger.info("Starting retrain task: %s", " ".join(cmd))
        env = os.environ.copy()
        env.setdefault("SKIP_ML_LOAD", "true")
        env.setdefault("ENABLE_SHAP", "false")
        completed = subprocess.run(
            cmd,
            cwd=os.getcwd(),
            env=env,
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )

        if completed.returncode != 0:
            logger.error("Retrain failed: %s", completed.stderr)
            raise RuntimeError(completed.stderr[-2000:] or "Retrain model failed")

        ml_service = current_app.config.get("ML_SERVICE")
        if ml_service:
            ml_service.load_all_models()

        self.update_state(state="PROGRESS", meta={"progress": 100, "step": "retrain_model"})
        return {
            "success": True,
            "model_version": version,
            "feature_schema_version": "v3.0.0",
            "training_date": datetime.utcnow().isoformat(),
            "status": "completed",
            "stdout": completed.stdout[-2000:],
        }

    return _run_with_app_context(_run)
