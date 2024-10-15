import os
import pytest
import boto3
import logging
from unittest.mock import patch, Mock, MagicMock
from unittest import TestCase
from moto import mock_aws
from cyberark_onboard_workflow.main import (
    remove_access_key,
    NonRetriableError,
    lambda_handler,
    launch_workflow,
)
from cyberark_onboard_workflow.cyberark_workflow_api import (
    GetWorkflowError,
    GetLaunchWorkflowAuthError,
    GetLaunchWorkflowRetriableError,
)
from common_sailpoint_cyberark.auth import GetDagTokenError


@patch("cyberark_onboard_workflow.main.get_dag_token_for_cyberark")
@patch("cyberark_onboard_workflow.main.call_get_launch_workflow")
class TestLaunchWorflow(TestCase):
    def test_launch_workflow_dag_failure(
        self, mock_call_get_launch_workflow, mock_get_dag_token_for_cyberark
    ):
        mock_get_dag_token_for_cyberark.side_effect = GetDagTokenError
        with pytest.raises(Exception) as exception_info:
            launch_workflow({}, {})
        assert exception_info.type == GetDagTokenError

    def test_launch_workflow_auth_failure(
        self, mock_call_get_launch_workflow, mock_get_dag_token_for_cyberark
    ):
        mock_get_dag_token_for_cyberark.return_value = "token"
        mock_call_get_launch_workflow.side_effect = GetLaunchWorkflowAuthError
        with pytest.raises(Exception) as exception_info:
            launch_workflow({}, {})
        assert exception_info.type == GetLaunchWorkflowAuthError

    def test_launch_workflow_workflow_failure(
        self, mock_call_get_launch_workflow, mock_get_dag_token_for_cyberark
    ):
        mock_get_dag_token_for_cyberark.return_value = "token"
        mock_call_get_launch_workflow.side_effect = GetWorkflowError
        with pytest.raises(Exception) as exception_info:
            launch_workflow({}, {})
        assert exception_info.type == GetWorkflowError

    def test_launch_workflow_retriable_error(
        self, mock_call_get_launch_workflow, mock_get_dag_token_for_cyberark
    ):
        mock_get_dag_token_for_cyberark.return_value = "token"
        mock_call_get_launch_workflow.side_effect = GetLaunchWorkflowRetriableError
        with pytest.raises(Exception) as exception_info:
            launch_workflow({}, {})
        assert exception_info.type == GetLaunchWorkflowRetriableError

    def test_launch_workflow_success(
        self, mock_call_get_launch_workflow, mock_get_dag_token_for_cyberark
    ):
        mock_get_dag_token_for_cyberark.return_value = "token"
        mock_call_get_launch_workflow.return_value = 200, {"status": "success"}
        status, response = launch_workflow({}, {})
        assert status == 200
        assert response == {"status": "success"}


@patch("cyberark_onboard_workflow.main.configure_logger")
@patch("cyberark_onboard_workflow.main.Config")
@patch("cyberark_onboard_workflow.main.get_dag_token_for_cyberark")
@patch("cyberark_onboard_workflow.main.call_get_launch_workflow")
@patch("cyberark_onboard_workflow.main.remove_access_key")
class TestLambdaHandler(TestCase):
    def setUp(self):
        self.event = {
            "cyberark_state_enabled": True,
            "cross_account_iam_role": "test_role",
            "workspace_metadata": {"response_elements": [{"account_id": "695547869248"}]},
            "iam_details": {"iam_user_name": "test_user"},
        }

    def test_lambda_handler_dag_token_error(
        self,
        mock_remove_access_key,
        mock_call_get_launch_workflow,
        mock_get_dag_token_for_cyberark,
        mock_Config,
        mock_configure_logger,
    ):
        mock_configure_logger.return_value = mock_configure_logger
        mock_Config.return_value = mock_Config
        mock_get_dag_token_for_cyberark.side_effect = GetDagTokenError
        mock_remove_access_key.return_value = None
        with pytest.raises(Exception) as exception_info:
            lambda_handler(self.event, {})
        assert exception_info.type == NonRetriableError
        mock_remove_access_key.assert_called_once()

    def test_lambda_handler_workflow_error(
        self,
        mock_remove_access_key,
        mock_call_get_launch_workflow,
        mock_get_dag_token_for_cyberark,
        mock_Config,
        mock_configure_logger,
    ):
        mock_configure_logger.return_value = mock_configure_logger
        mock_Config.return_value = mock_Config
        mock_get_dag_token_for_cyberark.return_value = "token"
        mock_call_get_launch_workflow.side_effect = GetWorkflowError
        mock_remove_access_key.return_value = None
        with pytest.raises(Exception) as exception_info:
            lambda_handler(self.event, {})
        assert exception_info.type == NonRetriableError
        mock_remove_access_key.assert_called_once()

    def test_lambda_handler_workflow_auth_error(
        self,
        mock_remove_access_key,
        mock_call_get_launch_workflow,
        mock_get_dag_token_for_cyberark,
        mock_Config,
        mock_configure_logger,
    ):
        mock_configure_logger.return_value = mock_configure_logger
        mock_Config.return_value = mock_Config
        mock_get_dag_token_for_cyberark.return_value = "token"
        mock_call_get_launch_workflow.side_effect = GetLaunchWorkflowAuthError
        mock_remove_access_key.return_value = None
        with pytest.raises(Exception) as exception_info:
            lambda_handler(self.event, {})
        assert exception_info.type == NonRetriableError
        mock_remove_access_key.assert_called_once()

    def test_lambda_handler_workflow_retriable_error(
        self,
        mock_remove_access_key,
        mock_call_get_launch_workflow,
        mock_get_dag_token_for_cyberark,
        mock_Config,
        mock_configure_logger,
    ):
        mock_configure_logger.return_value = mock_configure_logger
        mock_Config.return_value = mock_Config
        mock_get_dag_token_for_cyberark.return_value = "token"
        mock_call_get_launch_workflow.side_effect = GetLaunchWorkflowRetriableError
        mock_remove_access_key.return_value = None
        with pytest.raises(Exception) as exception_info:
            lambda_handler(self.event, {})
        assert exception_info.type == NonRetriableError
        mock_remove_access_key.assert_called_once()

    def test_lambda_handler_workflow_200_success(
        self,
        mock_remove_access_key,
        mock_call_get_launch_workflow,
        mock_get_dag_token_for_cyberark,
        mock_Config,
        mock_configure_logger,
    ):
        mock_configure_logger.return_value = mock_configure_logger
        mock_Config.return_value = mock_Config
        mock_get_dag_token_for_cyberark.return_value = "token"
        mock_call_get_launch_workflow.return_value = 200, {
            "status": "success",
            "requestId": "1234",
        }
        mock_remove_access_key.return_value = None
        task_result_id = lambda_handler(self.event, {})
        mock_remove_access_key.assert_not_called()
        assert task_result_id == {"cyberark_taskresult_id": "1234"}

    def test_lambda_handler_workflow_409_success(
        self,
        mock_remove_access_key,
        mock_call_get_launch_workflow,
        mock_get_dag_token_for_cyberark,
        mock_Config,
        mock_configure_logger,
    ):
        mock_configure_logger.return_value = mock_configure_logger
        mock_Config.return_value = mock_Config
        mock_get_dag_token_for_cyberark.return_value = "token"
        mock_call_get_launch_workflow.return_value = 409, {
            "status": "success",
            "requestId": "1234",
        }
        mock_remove_access_key.return_value = None
        task_result_id = lambda_handler(self.event, {})
        mock_remove_access_key.assert_not_called()
        assert task_result_id == {"cyberark_taskresult_id": "1234"}


def test_remove_access_key(caplog):
    caplog.set_level(logging.INFO)
    with mock_aws():
        iam_client = boto3.client("iam")
        os.environ["MOTO_ACCOUNT_ID"] = "695547869248"
        user_response = iam_client.create_user(UserName="test_user")
        iam_client.create_access_key(UserName=user_response["User"]["UserName"])
        event = {
            "workspace_metadata": {"response_elements": [{"account_id": "695547869248"}]},
            "cross_account_iam_role": "test_role",
            "iam_details": {"iam_user_name": "test_user"},
        }
        remove_access_key(event)
        list_key_response = iam_client.list_access_keys(UserName=user_response["User"]["UserName"])
        assert "Access key deleted successfully" in caplog.text
        assert len(list_key_response["AccessKeyMetadata"]) == 0


def test_remove_access_key_no_keys(caplog):
    caplog.set_level(logging.INFO)
    with mock_aws():
        iam_client = boto3.client("iam")
        os.environ["MOTO_ACCOUNT_ID"] = "695547869248"
        iam_client.create_user(UserName="test_user")
        event = {
            "workspace_metadata": {"response_elements": [{"account_id": "695547869248"}]},
            "cross_account_iam_role": "test_role",
            "iam_details": {"iam_user_name": "test_user"},
        }
        remove_access_key(event)
        assert "No access key found, not deleting any key" in caplog.text


def test_remove_access_key_2_keys(caplog):
    caplog.set_level(logging.ERROR)
    with mock_aws():
        iam_client = boto3.client("iam")
        os.environ["MOTO_ACCOUNT_ID"] = "695547869248"
        user_response = iam_client.create_user(UserName="test_user")
        iam_client.create_access_key(UserName=user_response["User"]["UserName"])
        iam_client.create_access_key(UserName=user_response["User"]["UserName"])
        event = {
            "workspace_metadata": {"response_elements": [{"account_id": "695547869248"}]},
            "cross_account_iam_role": "test_role",
            "iam_details": {"iam_user_name": "test_user"},
        }
        with pytest.raises(Exception) as exception_info:
            remove_access_key(event)
        assert exception_info.type == NonRetriableError
        assert "More than 1 access key found, not deleting any key" in caplog.text


def test_remove_access_key_no_user(caplog):
    caplog.set_level(logging.ERROR)
    with mock_aws():
        os.environ["MOTO_ACCOUNT_ID"] = "695547869248"
        event = {
            "workspace_metadata": {"response_elements": [{"account_id": "695547869248"}]},
            "cross_account_iam_role": "test_role",
            "iam_details": {"iam_user_name": "test_user"},
        }
        with pytest.raises(Exception) as exception_info:
            remove_access_key(event)
        assert exception_info.type == NonRetriableError
        assert (
            "Unexpected error: An error occurred (NoSuchEntity) when calling the ListAccessKeys operation: The user with name test_user cannot be found."
            in caplog.text
        )
