#!/usr/bin/env python
"""
Run Risk Scoring and Recommendations pipeline directly.
Calculates churn risk scores, generates SHAP explanation cache,
and builds action recommendations for all eligible customers.
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.services.pipeline_service import PipelineService
from app.services.recommendation_service import RecommendationContextService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    app = create_app()
    with app.app_context():
        logger.info("=== STEP 5: RUNNING RISK SCORING & SHAP EXPLANATIONS ===")
        pipeline_service = PipelineService()
        scoring_res = pipeline_service.run_scoring()
        logger.info("Scoring result: %s", scoring_res)

        logger.info("=== STEP 6: RUNNING RECOMMENDATION CONTEXT ENGINE ===")
        rec_service = RecommendationContextService()
        rec_res = rec_service.backfill_latest()
        logger.info("Recommendations result: %s", rec_res)

        logger.info("=== PIPELINE EXECUTION FINISHED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
