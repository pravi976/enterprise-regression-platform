def execute(input_payload, context):
    """Example service-owned executor returning actual output for comparison."""
    return {
        "body": {
            "customerId": input_payload["customerId"],
            "recommendationCount": 2,
            "source": "team-python-executor",
        }
    }
