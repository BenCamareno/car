import os
import sys
import pytest
from unittest.mock import MagicMock, patch
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../lambda')))
from ad_provisioner_api.adprovisioner.group_provisioner import GroupRequest
from ldap3 import Connection
 
LOCAL_GROUP = -2147483644
GLOBAL_GROUP = -2147483646
 
# Test data
workspace_name = "test_workspace"
ou_container_dn = "OU=test_container,DC=example,DC=com"
group_object_class = "group"
roles = ["Admin", "User"]
group_category = "Workspaces"
attributes = {"description": "Test group"}
sailpoint_enabled = True
all_groups_dn = "CN=All Groups,DC=example,DC=com"
 
@pytest.fixture
def group_request():
    return GroupRequest()
 
@patch("ad_provisioner_api.adprovisioner.utils.get_ws_shortname")
@patch("ad_provisioner_api.adprovisioner.utils.get_entry")
@patch("ad_provisioner_api.adprovisioner.utils.add_entry")
def test_create_ws_ou(mock_add_entry, mock_get_entry, mock_get_ws_shortname, group_request):
    connection = MagicMock(spec=Connection)
    mock_get_ws_shortname.return_value = "TESTWS"
    mock_get_entry.return_value = (None, "No Entry Found")
 
    result = group_request.create_ws_ou(connection, workspace_name, ou_container_dn)
 
    mock_get_entry.assert_called_once()
    mock_add_entry.assert_called_once()
    assert result == mock_add_entry.return_value
 
@patch("ad_provisioner_api.adprovisioner.utils.get_ws_shortname")
@patch("ad_provisioner_api.adprovisioner.utils.add_entry")
def test_create_groups(mock_add_entry, mock_get_ws_shortname, group_request):
    connection = MagicMock(spec=Connection)
    mock_get_ws_shortname.return_value = "TESTWS"
    mock_add_entry.return_value = True
 
    # Test with LOCAL_GROUP type
    group_request.create_groups(
        connection,
        workspace_name,
        ou_container_dn,
        group_object_class,
        roles,
        group_category,
        LOCAL_GROUP,
        attributes,
        sailpoint_enabled=sailpoint_enabled,
        all_groups_dn=all_groups_dn
    )
 
    mock_add_entry.assert_called()
 
    # Test with GLOBAL_GROUP type
    group_request.create_groups(
        connection,
        workspace_name,
        ou_container_dn,
        group_object_class,
        roles,
        group_category,
        GLOBAL_GROUP,  # Using mocked GLOBAL_GROUP
        attributes,
        sailpoint_enabled=sailpoint_enabled,
        all_groups_dn=all_groups_dn
    )
 
    mock_add_entry.assert_called()
 
@patch("ad_provisioner_api.adprovisioner.utils.get_ws_shortname")
@patch("ad_provisioner_api.adprovisioner.utils.recursive_delete")
def test_delete_groups(mock_recursive_delete, mock_get_ws_shortname, group_request):
    connection = MagicMock(spec=Connection)
    mock_get_ws_shortname.return_value = "TESTWS"
 
    group_request.delete_groups(connection, workspace_name, ou_container_dn)
 
    mock_recursive_delete.assert_called_once()
 
@patch("ad_provisioner_api.adprovisioner.utils.get_ws_shortname")
@patch("ad_provisioner_api.adprovisioner.utils.get_members_of_object")
def test_get_groups(mock_get_members_of_object, mock_get_ws_shortname, group_request):
    connection = MagicMock(spec=Connection)
    mock_get_ws_shortname.return_value = "TESTWS"
    mock_get_members_of_object.return_value = [{"dn": "CN=TestGroup,OU=TESTWS,DC=example,DC=com"}]
 
    result = group_request.get_groups(connection, workspace_name, ou_container_dn, group_object_class)
 
    mock_get_members_of_object.assert_called_once()
    assert result == ["CN=TestGroup,OU=TESTWS,DC=example,DC=com"]
 
