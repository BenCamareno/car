def process_get_onboarding_api_response(api_response: Dict):
    try:
        response = api_response
        sailpoint_status = response["sailPointStatus"]
        cyberark_error = response["cyberArkError"]
        if cyberark_error != "Null" or sailpoint_status == 500:
            logger.error("CyberArk role onboarding workflow terminated!")
            return OnboardingProcessingResult(status=OnboardingStatus.TERMINATED)
        if sailpoint_status == 201:
            return OnboardingProcessingResult(status=OnboardingStatus.IN_PROGRESS)
        if sailpoint_status == 200:
            return OnboardingProcessingResult(OnboardingStatus.SUCCEEDED)
        if cyberark_error == 409:
            return OnboardingProcessingResult(OnboardingStatus.SUCCEEDED)
        else:
            logger.error(
                "CyberArk role onboarding workflow completed but failed to onboard all roles."
            )
            return OnboardingProcessingResult(status=OnboardingStatus.FAILED)

    except InvalidResponseError as e:
        logger.exception(f"Invalid API response: {e!r}")
        return OnboardingProcessingResult(status=OnboardingStatus.INVALID_API_RESPONSE)
