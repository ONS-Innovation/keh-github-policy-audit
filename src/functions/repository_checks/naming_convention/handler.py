"""Lambda handler for the naming convention policy check."""

from policy_methods_library.checks.naming_convention import check_naming_convention


def handler(event, context):
    """Step Function invokes with {"repository_name": "..."}."""
    result = check_naming_convention(event["repository_name"])
    result["check_name"] = "naming_convention"
    return result
