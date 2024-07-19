import pytest
import sys
import os
from unittest.mock import patch, Mock, MagicMock
from common.config import Config
from common_sailpoint_cyberark.cyberark_api import (
    CyberArkApiError,
    CyberArkApiHttpAuthError,
    CyberArkApiHttpNotFoundError,
)
from cyberark_onboard_workflow.cyberark_workflow_api import (
    call_get_launch_workflow,
    GetLaunchWorkflowAuthError,
    GetLaunchWorkflowRetriableError,
)

payload = {
    "secret_name_cbainet_configs": "/CNS/identitystatemachine/cbainet_configs",
    "secret_name_cert_configs": "/CNS/identitystatemachine/certificates",
    "role_name": "Workspace Admin",
    "role_type": "WS",
    "workspace_metadata": {
        "request_parameters": {"account_id": "1234567890"},
        "response_elements": [
            {
                "ci_number": "CM294588",
                "account_id": "1234567890",
                "release_channel": "preview",
                "service_tier": "nonp",
                "workspace_type": "tenant",
                "workspace_status": "provisioned",
                "workspace_variables": {
                    "cf_stack_name_prefix": "cns-{{ workspace_name | regex_replace('_') }}",
                    "workspace_ci_number": "PV0000002",
                    "ic_cidr_b2": "0.0.0.0/0",
                    "sec_cidr_a1": "192.168.2.0/28",
                    "sec_cidr_a2": "0.0.0.0/0",
                    "tgw_cidr_c1": "100.64.0.32/28",
                    "ic_cidr_b1": "192.168.1.144/28",
                    "workspace_account_id": "1234567890",
                    "workspace_type": "tenant",
                    "res_cidr_b1": "192.168.1.208/28",
                    "res_cidr_b2": "0.0.0.0/0",
                    "workspace_email": "awspv0001@cba.com.au",
                    "ic_cidr_c1": "192.168.1.160/28",
                    "ic_cidr_c2": "0.0.0.0/0",
                    "tgw_cidr_b1": "100.64.0.16/28",
                    "business_service": "preview",
                    "cidr_block": [
                        "192.168.1.128/28",
                        "192.168.1.144/28",
                        "192.168.1.160/28",
                        "192.168.1.192/28",
                        "192.168.1.208/28",
                        "192.168.1.224/28",
                        "192.168.2.0/28",
                        "192.168.2.16/28",
                        "192.168.2.32/28",
                        "192.168.2.64/28",
                        "192.168.2.80/28",
                        "192.168.2.96/28",
                        "192.168.2.192/28",
                        "192.168.2.208/28",
                        "192.168.2.224/28",
                        "192.168.2.128/28",
                        "192.168.2.144/28",
                        "192.168.2.160/28",
                        "100.64.0.0/26",
                    ],
                    "customer_specific_delineation": "previewworkspaces2",
                    "ecif_cidr_c2": "0.0.0.0/0",
                    "res_cidr_c1": "192.168.1.224/28",
                    "mgmt_cidr_c1": "192.168.2.96/28",
                    "res_cidr_c2": "0.0.0.0/0",
                    "eccf_cidr_c2": "0.0.0.0/0",
                    "ecif_cidr_c1": "192.168.2.160/28",
                    "workspace_release_channel": "preview",
                    "eccf_cidr_c1": "192.168.2.224/28",
                    "mgmt_cidr_c2": "0.0.0.0/0",
                    "custom_repo_branch_version": "master",
                    "tgw_cidr_a1": "100.64.0.0/28",
                    "workspace_alias": "cba-a-np-0000002-is-lab-preview_workspaces2",
                    "cns_ad_group_name": "cba-a-np-0000002-is-lab-preview_workspaces2",
                    "sec_cidr_c1": "192.168.2.32/28",
                    "sec_cidr_c2": "0.0.0.0/0",
                    "workspace_service_tier": "nonp",
                    "zone_name": "ispreviewworkspaces201.aws.beta.au.internal.cba",
                    "custom_repo_name": "cba-a-is-preview_workspaces2-custom",
                    "ecif_cidr_b1": "192.168.2.144/28",
                    "ecif_cidr_b2": "0.0.0.0/0",
                    "eccf_cidr_b1": "192.168.2.208/28",
                    "eccf_cidr_b2": "0.0.0.0/0",
                    "mgmt_cidr_b1": "192.168.2.80/28",
                    "mgmt_cidr_b2": "0.0.0.0/0",
                    "workspace_name": "cba-a-np-0000002-is-lab-preview_workspaces2",
                    "has_network": True,
                    "ic_cidr_a1": "192.168.1.128/28",
                    "sec_cidr_b1": "192.168.2.16/28",
                    "ic_cidr_a2": "0.0.0.0/0",
                    "sec_cidr_b2": "0.0.0.0/0",
                    "business_platform": "is",
                    "eccf_cidr_a2": "0.0.0.0/0",
                    "ecif_cidr_a1": "192.168.2.128/28",
                    "eccf_cidr_a1": "192.168.2.192/28",
                    "workspace_region": "ap-southeast-2",
                    "mgmt_cidr_a2": "0.0.0.0/0",
                    "res_cidr_a1": "192.168.1.192/28",
                    "mgmt_cidr_a1": "192.168.2.64/28",
                    "res_cidr_a2": "0.0.0.0/0",
                    "ecif_cidr_a2": "0.0.0.0/0",
                },
                "workspace_descriptor": {
                    "metadata": {
                        "application_environment": "preview",
                        "service_ci": "CI000109905",
                        "business_justification": "Needed to support the Engineering practices-Test",
                        "workspace_description": "test LZ",
                        "workspace_type": "tenant",
                        "req_number": "REQ3568925",
                        "service_environment": "Non-Production",
                        "release_channel": "preview",
                        "platform_shortname": "cio4tech",
                        "ci_number": "PV0000002",
                        "ritm_number": "RITM90000091",
                        "workspace_name": "cba-a-np-0000002-is-lab-preview_workspaces2",
                        "contacts": {
                            "email_distribution": "yash.cba.com.au",
                            "application_owner_email": "Aaron.Gibbs@cba.com.au",
                        },
                        "cost_centre": "123456",
                    },
                    "workspace_components": {
                        "tenant_enablement": {
                            "version": "1.0.0",
                            "properties": {},
                            "module_id": "tenant_enablement",
                        },
                        "network_security_groups": {
                            "version": "1.0.0",
                            "properties": {
                                "role": "cns-nexus-buildrole-network-security-groups",
                                "role_stack_file": "network-security-groups.yml",
                            },
                            "module_id": "network_security_groups",
                        },
                        "identity_access": {
                            "version": "1.0.0",
                            "properties": {},
                            "module_id": "identity_access",
                        },
                        "network_tgws": {
                            "version": "1.0.0",
                            "properties": {
                                "role": "cns-nexus-buildrole-network-tgws",
                                "role_stack_file": "network-tgws.yml",
                            },
                            "module_id": "network_tgws",
                        },
                        "lmi_ob": {
                            "version": "1.0.0",
                            "properties": {
                                "role": "cns-nexus-buildrole-lmi-ob",
                                "role_stack_file": "lmi-ob.yml",
                            },
                            "module_id": "lmi_ob",
                        },
                        "workspace_bootstrap": {
                            "version": "1.0.0",
                            "properties": {},
                            "module_id": "workspace_bootstrap",
                        },
                        "network_r53_vpce": {
                            "version": "1.0.0",
                            "properties": {
                                "role": "cns-nexus-buildrole-network-r53-vpce",
                                "role_stack_file": "network-r53-vpce.yml",
                            },
                            "module_id": "network_r53_vpce",
                        },
                        "cv_control": {
                            "version": "1.0.0",
                            "properties": {
                                "role": "cns-nexus-buildrole-cv-control",
                                "role_stack_file": "cv-control.yml",
                            },
                            "module_id": "cv_control",
                        },
                        "qualys_automation": {
                            "version": "1.0.0",
                            "properties": {},
                            "module_id": "qualys_automation",
                        },
                        "workspace_uat": {
                            "version": "1.0.0",
                            "properties": {
                                "role": "cns-nexus-buildrole-workspace-uat",
                                "role_stack_file": "workspace-uat.yml",
                            },
                            "module_id": "workspace_uat",
                        },
                        "workspace_base": {
                            "version": "1.0.0",
                            "properties": {},
                            "module_id": "workspace_base",
                        },
                        "workspace_deployIamRoles": {
                            "version": "1.0.0",
                            "properties": {},
                            "module_id": "workspace_deployIamRoles",
                        },
                    },
                    "request_repository": {
                        "json_file": "cba-a-np-0000002-is-lab-preview_workspaces2.json",
                        "type": "service_now",
                        "repository_name": "cns-aws-onboarding-test",
                        "branch_name": "PV0000002",
                    },
                    "configuration": {
                        "ad_groups": {
                            "VM_SLG": [
                                "SLG-VM-cba-a-np-unknownocd-asdf-Admin",
                                "SLG-VM-cba-a-np-unknownocd-asdf-Puser",
                                "SLG-VM-cba-a-np-unknownocd-asdf-User",
                            ],
                            "VM_SGG": [
                                "SGG-VM-cba-a-np-unknownocd-asdf-Admin",
                                "SGG-VM-cba-a-np-unknownocd-asdf-Puser",
                                "SGG-VM-cba-a-np-unknownocd-asdf-User",
                            ],
                            "WS_SGG": [
                                "SGG-WS-cba-a-np-unknownocd-asdf-Admin",
                                "SGG-WS-cba-a-np-unknownocd-asdf-Puser",
                                "SGG-WS-cba-a-np-unknownocd-asdf-User",
                            ],
                        },
                        "has_network": True,
                        "patching_configuration": {
                            "day": "Thursday",
                            "frequency": "Monthly",
                            "time": "15:00",
                        },
                        "onboarding_users": {
                            "server_power_user": [],
                            "workspace_user": [],
                            "workspace_administrator": [],
                            "workspace_power_user": [],
                            "server_user": [],
                            "server_administrator": [],
                        },
                        "number_of_azs": 1,
                        "custom_repo": {"custom_repo_name": "", "custom_repo_mapping": True},
                        "hosted_zone": "PV0000002",
                        "backup_preferences": {
                            "is_backup_needed": "Yes, everything that Commvault supports to backup",
                            "eir_hir_status": "",
                            "backup_start_time": "17:00",
                            "services_selected": "",
                            "long_term_retention": "No",
                            "rds_engine_selected": "RDS_Oracle",
                        },
                        "github_cloud": {
                            "organisation": "",
                            "repo_name": "",
                            "is_onboarding": True,
                        },
                        "enable_tbv": True,
                        "cidr": {
                            "internally_controlled_hosts": "/28",
                            "externally_controlled_if_hosts": "/28",
                            "secured_hosts": "/28",
                            "externally_controlled_vpc_hosts": "/28",
                            "restricted_hosts": "/28",
                            "management_hosts": "/28",
                        },
                        "pooled_workspace": True,
                        "approved_design_artifact": {
                            "approval_date_for_design": "",
                            "url_to_design_artifact": "",
                            "name_of_design_artifact": "",
                        },
                    },
                },
            }
        ],
    },
    "role": {
        "role_name": "Workspace Admin",
        "role_type": "WS",
        "privileged_category": "PRIVILEGED",
        "permission_set": "admin-user-assume-all",
        "ad_group_suffix": "Admin",
        "ad_group_name": "SGG-WS-cba-a-cl-0000205-User",
        "ad_group_name1": "Placeholder AD Group",
        "identitystore_group_id": {"identitystore_group_id": ""},
        "ps_assignment_status": {"ps_assignment_status": "sso not enabled"},
        "iam_details": {
            "access_key_id": "",
            "secret_key_encrypted": "MIIB0wYJKoZIhvcNAQcDoIIBxDCCAcACAQAxggFLMIIBRwIBADAvMBsxGTAXBgNVBAMMEENBRW5jcnlwdGlvbkNlcnQCEDUr0fEA4QKYR+iHyugUX4QwDQYJKoZIhvcNAQEHMAAEggEAi2yrh8eceU7atQjk9XgkN4UmisTo1EWHkVRE0+U0jJc5NWi7tK9lYaO9lnEiCtwat12B9snzZmrCaIU5/WPOC9SOvYCwx66qVaZ/RkhP0tIzF43+6syzts5KpN9fL/VYfnMqDhFeeNnRZasqmU6U2AN6oqNmZNes0cY3+T5ZO11aup8Q/bjV2J5QVeccCvqvPoD8nAM/swJ1IoWmn/PtOImI/TG+DbVzGg3z/2vxE9GrSktiLHxEgK0AQi9NxEfN+JQnU7SyKb4s467TO2EUSWumNKogcP/dHuF25F6oxZC+Wkt0sPIIeMLJRzH7t6XD6fjDHFoQ9dM0uzjIm0acdjBsBgkqhkiG9w0BBwEwHQYJYIZIAWUDBAEqBBAM3zcxVdd5/qXrigEEihhJgEBY4wehYYsZcRNtmoP4nCddfkSF3BfAptQZbzSLobrmnNlL2cDeJixBSBqJdVOHa1//mFCJqwsOpr9gzethg6NB",
            "role_arn": "arn:aws:iam::123456789016:role/IAMTestRole",
        },
    },
    "ad_group_suffix": "Admin",
    "cyberark_state_enabled": "true",
}


def assert_call_cyberark_api_called_once_with(mock_call, gidp_token, mock_config):
    """
    Helper function to assert the call arguments for call_cyberark_api
    """
    expected_url = f"{mock_config.dag.dag_api_baseurl}{mock_config.cyberark.status_endpoint}"
    expected_args = {
        "url": expected_url,
        "gidp_token": gidp_token,
        "method": "POST",
        "payload": payload,
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
    mock_config.cyberark.status_endpoint = "/workforce-privileged-access-management/pam/onboard"
    mock_config.dag.identity_ssl_cert_public_key_temp_filepath = "/public_key.pem"
    mock_config.dag.identity_ssl_cert_private_key_content = "private_key_content"
    mock_config.ca_cert_temp_filepath = "/ca_cert.pem"
    mock_config.sailpoint.log_api_call_details = True
    return mock_config


@pytest.fixture
def mock_payload():
    mock_payload = payload
    return mock_payload


@pytest.fixture
def gidp_token():
    return "test_token"


def mock_call_cyberark_api_success(*args, **kwargs):
    mock_response = Mock()
    mock_response.status_code = 200
    # mock_response.json.return_value = {"status": "success"}
    return mock_response


def mock_call_cyberark_api_non_200(*args, **kwargs):
    mock_response = Mock()
    mock_response.status_code = 400
    # mock_response.json.return_value = {"error": "not found"}
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
        (mock_call_cyberark_api_non_200, GetLaunchWorkflowRetriableError),
        (mock_call_cyberark_api_auth_error, GetLaunchWorkflowAuthError),
        (mock_call_cyberark_api_not_found_error, GetLaunchWorkflowRetriableError),
        (mock_call_cyberark_api_generic_error, GetLaunchWorkflowRetriableError),
    ],
)
@patch("cyberark_onboard_workflow.cyberark_workflow_api.call_cyberark_api")
def test_call_get_onboarding_result_api(
    mock_call_cyberark_api, side_effect, expected_exception, gidp_token, mock_config
):
    mock_call_cyberark_api.side_effect = side_effect

    if expected_exception:
        with pytest.raises(expected_exception):
            call_get_launch_workflow(gidp_token, mock_config, mock_payload)
    else:
        result = call_get_launch_workflow(gidp_token, mock_config)
        assert result == {"status": "success"}

    assert_call_cyberark_api_called_once_with(mock_call_cyberark_api, gidp_token, mock_config)
