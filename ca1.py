import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List

from common.config import Config
from common_sailpoint_cyberark.cyberark_api import (
    call_cyberark_api,
    CyberArkApiHttpAuthError,
    CyberArkApiHttpNotFoundError,
    CyberArkApiError,
)
from common_sailpoint_cyberark.cyberark_api_response.formatted_message import FormattedMessage
from common_sailpoint_cyberark.cyberark_api_response.response import (
    Response,
    CompletionStatus,
    InvalidResponseError,
)
from common_sailpoint_cyberark.cyberark_api_response.response_analyser import (
    ResponseAnalyser,
    Entity,
)

logger = logging.getLogger()

class GetTaskResultApiError(Exception):
    pass

class GetTaskResultApiRetriableError(GetTaskResultApiError):
    pass

class GetTaskResultApiNonRetriableError(GetTaskResultApiError):
    pass

class GetTaskResultApiAuthError(GetTaskResultApiRetriableError):
    pass

class GetTaskResultApiNotFoundError(GetTaskResultApiNonRetriableError):
    pass

class TaskResultStatus(Enum):
    IN_PROGRESS = auto()
    TERMINATED = auto()
    SUCCEEDED = auto()
    FAILED = auto()
    INVALID_API_RESPONSE = auto()

@dataclass
class TaskResultProcessingResult:
    status: TaskResultStatus
    error_details: Dict[Entity, List[FormattedMessage]] = field(default_factory=dict)

def call_get_task_result_api(task_result_id, gidp_token, config: Config):
    logger.info(f"Calling CyberArk GET TaskResults API for TaskResult ID: {task_result_id}")
    url = f"{config.dag.dag_api_baseurl}{config.cyberark.taskresults_endpoint}/{task_result_id}"
    try:
        response = call_cyberark_api(
            url=url,
            gidp_token=gidp_token,
            method="GET",
            payload=None,
            client_public_cert_path=config.dag.identity_ssl_cert_public_key_temp_filepath,
            client_private_key_content=config.dag.identity_ssl_cert_private_key_content,
            ca_cert_path=config.ca_cert_temp_filepath,
            log_details=config.cyberark.log_api_call_details,
        )
        if response.status_code != 200:
            logger.error(
                f"CyberArk GET TaskResults API was successful but received non-200 response: "
                f"{response.status_code}. Response: {response.json()}"
            )
            raise GetTaskResultApiRetriableError(
                f"Received non-200 response {response.status_code} for GET TaskResults"
            )
        logger.info(f"Successfully retrieved CyberArk TaskResults: {response.json()}")
        return response.json()
    except CyberArkApiHttpAuthError as ex:
        raise GetTaskResultApiAuthError(
            "Failed to call CyberArk TaskResults endpoint due to authentication error"
        ) from ex
    except CyberArkApiHttpNotFoundError as ex:
        raise GetTaskResultApiNotFoundError(
            "Failed to call CyberArk TaskResults endpoint due to resource not found error"
        ) from ex
    except CyberArkApiError as ex:
        raise GetTaskResultApiRetriableError(
            "Failed to call CyberArk TaskResults endpoint"
        ) from ex

def process_get_task_result_api_response(api_response: Dict):
    try:
        response = Response(response=api_response)
        if response.terminated:
            logger.error("CyberArk role onboarding workflow terminated!")
            return TaskResultProcessingResult(status=TaskResultStatus.TERMINATED)
        if response.is_in_progress():
            return TaskResultProcessingResult(status=TaskResultStatus.IN_PROGRESS)

        response_analyser = ResponseAnalyser(response)
        errors = response_analyser.get_errors()
        _log_errors_if_any(errors)
        if response.completion_status == CompletionStatus.SUCCESS:
            # workflow completed (maybe with some errors)
            if response_analyser.is_all_roles_onboarded():
                logger.info("CyberArk role onboarding workflow completed successfully.")
                return TaskResultProcessingResult(
                    status=TaskResultStatus.SUCCEEDED, error_details=errors
                )
            else:
                logger.error(
                    "CyberArk role onboarding workflow completed but failed to onboard all roles."
                )
                return TaskResultProcessingResult(
                    status=TaskResultStatus.FAILED, error_details=errors
                )

        # workflow failed to complete
        _log_warning_if_non_error_completion_status(response)
        logger.error(
            f"CyberArk role onboarding workflow failed with completion-status: "
            f"{response.completion_status.value}"
        )
        return TaskResultProcessingResult(status=TaskResultStatus.FAILED, error_details=errors)
    except InvalidResponseError as e:
        logger.exception(f"Invalid API response: {e!r}")
        return TaskResultProcessingResult(status=TaskResultStatus.INVALID_API_RESPONSE)

def _log_warning_if_non_error_completion_status(response):
    if response.completion_status != CompletionStatus.ERROR:
        # Note: Only ERROR is expected here, but if happened we deal with it like error.
        logger.warning(
            f"Received a completion-status other than Success/Error: '{response.completion_status.value}'"
        )

def _log_errors_if_any(errors: Dict[Entity, List[FormattedMessage]]):
    for entity, messages in errors.items():
        logger.error(
            f"Error in {entity.type_.name} '{entity.name}': {[msg.message for msg in messages]}"
        )