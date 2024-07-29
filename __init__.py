import pytest
from unittest.mock import patch, Mock, MagicMock
from common.config import Config
from common_sailpoint_cyberark.cyberark_api import (
    CyberArkApiError,
    CyberArkApiHttpAuthError,
    CyberArkApiHttpNotFoundError,
)
from get_cyberark_onboarding_result.onboarding_result_api import (
    call_get_onboarding_result_api,
    process_get_onboarding_api_response,
    GetLaunchWorkflowApiAuthError,
    GetLaunchWorkflowApiRetriableError,
    OnboardingStatus,
    OnboardingProcessingResult,
    InvalidResponseError,
)


def assert_call_cyberark_api_called_once_with(mock_call, gidp_token, mock_config):
    """
    Helper function to assert the call arguments for call_cyberark_api
    """
    expected_url = f"{mock_config.dag.dag_api_baseurl}{mock_config.cyberark.status_endpoint}"
    expected_args = {
        "url": expected_url,
        "gidp_token": gidp_token,
        "method": "GET",
        "payload": "",
        "client_public_cert_path": mock_config.dag.identity_ssl_cert_public_key_temp_filepath,
        "client_private_key_content": mock_config.dag.identity_ssl_cert_private_key_content,
        "ca_cert_path": mock_config.ca_cert_temp_filepath,
        "log_details": mock_config.sailpoint.log_api_call_details,
    }
    actual_args = mock_call.call_args_list[0][1]

    assert expected_args == actual_args


@pytest.fixture
def mock_config():
    mock_config = Mock(spec=Config)
    mock_config.dag.dag_api_baseurl = "https://test01.identity.test.aws.groupapi.cba"
    mock_config.cyberark.status_endpoint = "/workforce-privileged-access-management/pam/request/452"
    mock_config.dag.identity_ssl_cert_public_key_temp_filepath = "/public_key.pem"
    mock_config.dag.identity_ssl_cert_private_key_content = "private_key_content"
    mock_config.ca_cert_temp_filepath = "/ca_cert.pem"
    mock_config.sailpoint.log_api_call_details = True
    return mock_config


@pytest.fixture
def gidp_token():
    return "test_token"

@pytest.fixture
def request_id():
    return "452"


def mock_call_cyberark_api_success(*args, **kwargs):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success"}
    return mock_response


def mock_call_cyberark_api_non_200(*args, **kwargs):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.json.return_value = {"error": "not found"}
    return mock_response


def mock_call_cyberark_api_auth_error(*args, **kwargs):
    raise CyberArkApiHttpAuthError


def mock_call_cyberark_api_not_found_error(*args, **kwargs):
    raise CyberArkApiHttpNotFoundError


def mock_call_cyberark_api_generic_error(*args, **kwargs):
    raise CyberArkApiError


@pytest.mark.parametrize(
    "side_effect,expected_exception",
    [
        (mock_call_cyberark_api_success, None),
        (mock_call_cyberark_api_non_200, GetLaunchWorkflowApiRetriableError),
        (mock_call_cyberark_api_auth_error, GetLaunchWorkflowApiAuthError),
        (mock_call_cyberark_api_not_found_error, GetLaunchWorkflowApiRetriableError),
        (mock_call_cyberark_api_generic_error, GetLaunchWorkflowApiRetriableError),
    ],
)
@patch("get_cyberark_onboarding_result.onboarding_result_api.call_cyberark_api")
def test_call_get_onboarding_result_api(
    mock_call_cyberark_api, side_effect, expected_exception, gidp_token, mock_config
):
    mock_call_cyberark_api.side_effect = side_effect

    if expected_exception:
        with pytest.raises(expected_exception):
            call_get_onboarding_result_api(request_id, gidp_token, mock_config)
    else:
        result = call_get_onboarding_result_api(request_id, gidp_token, mock_config)
        assert result == {"status": "success"}

    assert_call_cyberark_api_called_once_with(mock_call_cyberark_api, gidp_token, mock_config)


@pytest.mark.parametrize(
    "api_response,expected_status",
    [
        (lambda: MagicMock(terminated=True), OnboardingStatus.TERMINATED),
        (
            lambda: MagicMock(terminated=False, is_in_progress=lambda: True),
            OnboardingStatus.IN_PROGRESS,
        ),
        (
            lambda: MagicMock(terminated=False, is_in_progress=lambda: False),
            OnboardingStatus.FAILED,
        ),
        (
            lambda: MagicMock(
                terminated=False,
                is_in_progress=lambda: (_ for _ in ()).throw(InvalidResponseError),
            ),
            OnboardingStatus.INVALID_API_RESPONSE,
        ),
    ],
)
def test_process_get_onboarding_api_response(api_response, expected_status):
    response = api_response()
    result = process_get_onboarding_api_response(response)
    assert result == OnboardingProcessingResult(status=expected_status)

if __name__ == "__main__":
    pytest.main()
