"""Lambda handler for the naming convention policy check."""

import logging

from policy_methods_library.checks.naming_convention import check_naming_convention


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """Step Function invokes with {"repository_name": "..."}."""
    logger.info(f"Lambda invoked with event keys={sorted(event.keys())}")
    result = check_naming_convention(event["repository_name"])
    result["check_name"] = "naming_convention"
    logger.info(
        f"Lambda completed check={result['check_name']} result={result.get('result')}"
    )
    return result
