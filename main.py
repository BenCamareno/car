import logging
import time
from typing import Dict

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random,
    before_log,
    after_log,
)

from common.config import Config
from common.logger import configure_logger
from common_sailpoint_cyberark.auth import (
    sailpoint_authenticate,
    GetDagTokenError,
    GetSailpointTokenError,
)
from lambda_event import LambdaEvent, LambdaEventError
from task_result_api import (
    call_get_task_result_api,
    process_get_task_result_api_response,
    TaskResultStatus,
    GetTaskResultApiError,
    GetTaskResultApiRetriableError,
    GetTaskResultApiAuthError,
    GetTaskResultApiNotFoundError,
)

logger = logging.getLogger()


class OnboardingTaskNotCompleted(Exception):
    pass


class OnboardingTaskFailed(Exception):
    pass


class NonRetriableError(Exception):
    pass


class TaskResultNotFoundError(Exception):
    pass


def raise_for_unsuccessful_task_result(api_response: Dict):
    """
    Checks the task completion status and raise exception if it's not successfully completed, otherwise it
    returns.
    @param api_response: API response for Get TaskResult API call
    @raise OnboardingTaskFailed: if task terminated, failed to complete, or completed with error
    @raise OnboardingTaskNotCompleted: if task is still in progress,or API response is invalid
    """
    result = process_get_task_result_api_response(api_response)
    match result.status:
        case TaskResultStatus.SUCCEEDED:
            return
        case TaskResultStatus.IN_PROGRESS:
            raise OnboardingTaskNotCompleted("Workflow is still in progress")
        case TaskResultStatus.TERMINATED:
            raise OnboardingTaskFailed("Workflow terminated (terminated flag is set)")
        case TaskResultStatus.FAILED:
            error_messages = [
                f"{entity.type_.name} with name '{entity.name}':  {[msg.message for msg in messages]}"
                for entity, messages in result.error_details.items()
            ]
            raise OnboardingTaskFailed(f"Workflow failed. Errors: {error_messages}")
        case TaskResultStatus.INVALID_API_RESPONSE:
            # Although api response is invalid, but we need to retry again.
            raise OnboardingTaskNotCompleted(
                "Invalid API response received for Get TaskResult API. Try again later."
            )
        case _:
            raise RuntimeError(f"Unexpected value for Task Result Status: {result.status}")


# Note: we cannot apply conditional wait, so we implement short wait for Sailpoint Auth issue in tenacity and the long wait for non-auth issues via sleep().
@retry(
    retry=retry_if_exception_type(GetTaskResultApiRetriableError),
    reraise=True,
    stop=stop_after_attempt(Config.GET_TASK_RESULT_API_RETRY_SPEC.max_attempt_number),
    wait=wait_random(
        min=Config.GET_TASK_RESULT_API_RETRY_SPEC.wait_jitter_min,
        max=Config.GET_TASK_RESULT_API_RETRY_SPEC.wait_jitter_max,
    ),
    before=before_log(logger, logging.DEBUG),
    after=after_log(logger, logging.DEBUG),
)
def get_task_result(config: Config, task_result_id):
    logger.info(f"Task Result ID: {task_result_id}")
    try:
        gidp_token, sailpoint_token = sailpoint_authenticate(config)
    except (GetDagTokenError, GetSailpointTokenError) as ex:
        # Failed during authentication => no retry needed here as retry performed before
        logger.error(f"Authentication failed: {ex!r}")
        raise

    try:
        api_response = call_get_task_result_api(
            task_result_id, gidp_token, sailpoint_token, config
        )
        return api_response
    except GetTaskResultApiAuthError as ex:
        # Failed on Auth error => call authenticate() and repeat right away
        logger.error(f"GET TaskResult failed due to authentication error: {ex!r}")
        raise
    except GetTaskResultApiNotFoundError as ex:
        # Failed on NotFound (404) error => fail right away
        logger.error(f"GET TaskResult failed due to NotFound (404) error: {ex!r}")
        raise
    except GetTaskResultApiRetriableError as ex:
        # Failed on non-Auth retriable error => call authenticate() and repeat after delay
        logger.error(f"GET TaskResult failed with retriable error: {ex!r}")
        time.sleep(Config.GET_TASK_RESULT_API_RETRY_SPEC.wait_time)
        raise
    except GetTaskResultApiError as ex:
        # Failed on not (Auth | NotFound | retriable) error => it's non-retriable => fail right away
        logger.error(f"GET TaskResult failed with non-retriable error: {ex!r}")
        raise


def lambda_handler(event, context):
    """
    This function will make 3 API calls:
    1: authenticate against the Domain API Gateway & retrieve a DAG token
    2: use the token from step 1 to authenticate against Sailpoint & retrieve a Sailpoint token
    3: pass tokens from steps 1 and 2 so SailPoint API calls can be authenticated

    The function retries API call errors that can be recovered multiple times and if all retries failed it exists by
    raising NonRetriableError exception.
    For some errors like 404, invalid event, config, etc the function exists with NonRetriableError exception.
    If function receives the Task Result, and it shows task completed successfully, it finishes successfully by
    returning the Task result object.
    If function receives the Task Result, but it does not indicate successful task completion, the function terminates
    with either TaskFailed or TaskNotCompleted.
    The state machine is expected to retry the lambda on the following conditions:
    - TaskNotCompleted raised by lambda
    - Lambda could not complete due to timeout

    @param event: lambda event containing 'sailpoint_taskresult_id' and 'sailpoint_state_enabled
    @param context: standard lambda context

    @raise TaskResultNotFoundError: if failed to get task result due to NotFound 404 error
    @raise OnboardingTaskNotCompleted: if task result received but showing task is still in progress
    @raise OnboardingTaskFailed: if task result received but showing task failed to complete or completed with error
    @raise NonRetriableError: if an error occurred which cannot be recovered, or multiple retries for recovering an
    error failed so no more retries required from state machine
    @return: task result object received via API
    """

    logger.info(f"Lambda event: {event}")
    logger.info(f"Lambda context: {context}")

    config = None
    try:
        lambda_event = LambdaEvent(event)
        if not lambda_event.sailpoint_state_enabled:
            logger.info("Sailpoint API call is not enabled. Returning empty response ...")
            return {"role_onboarding_status": "COMPLETED"}

        config = Config()
        configure_logger(config.log_level)

        api_response = get_task_result(config, lambda_event.task_result_id)
        raise_for_unsuccessful_task_result(api_response)

        return {"role_onboarding_status": "COMPLETED"}
    except GetTaskResultApiNotFoundError as ex:
        logger.exception("Failed to retrieve task result due to NotFound (404) error")
        raise TaskResultNotFoundError(
            "Failed to retrieve task result due to NotFound (404) error"
        ) from ex
    except (GetDagTokenError, GetSailpointTokenError, GetTaskResultApiError) as ex:
        logger.exception("Failed to retrieve task result")
        raise NonRetriableError("Failed to get task result") from ex
    except (OnboardingTaskNotCompleted, OnboardingTaskFailed):
        logger.exception("Received task result, but task failed or not completed")
        raise
    except LambdaEventError as ex:
        logger.exception("Invalid Lambda event")
        raise NonRetriableError("Lambda failed due to invalid Lambda event") from ex
    except Exception as ex:
        logger.exception("Lambda failed with uncaught exception")
        raise NonRetriableError("Lambda failed with uncaught exception") from ex
    finally:
        if config:
            config.delete_all_temporary_files()
