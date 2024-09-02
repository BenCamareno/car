import logging
from . import utils

from ldap3 import Connection

logger = logging.getLogger(__name__)


class GroupRequest:
    """Interface for group request"""

    def __init__(
        self,
        account_id=None,
        request_number=None,
        description=None,
        native_ad=None,
        sailpoint_enabled=False,
        **attributes,
    ) -> None:
        self.account_id = account_id
        self.request_number = request_number
        self.description = description
        self.native_ad = native_ad
        self.sailpoint_enabled = sailpoint_enabled
        for k, v in attributes.items():
            setattr(self, k, v)

    # Create new workspace OU if it doesn't exist
    def create_ws_ou(
        self, connection: Connection, workspace_name: str, ou_container_dn: str
    ):
        workspace_ou = utils.get_ws_shortname(workspace_name=workspace_name).upper()

        full_group_container_dn = f"OU={workspace_ou},{ou_container_dn}"

        logger.info(f"Check if OU={workspace_ou} exists")
        ou_entry, message = utils.get_entry(
            connection=connection,
            base_dn=ou_container_dn,
            search_filter_type=utils.OU_FILTER,
            search_value=workspace_ou,
        )

        if not ou_entry:
            logger.info(f"Creating OU={workspace_ou}")
            ou_entry = utils.add_entry(
                connection=connection,
                dn=full_group_container_dn,
                object_class=utils.OU_OBJECT_CLASS,
                attributes={
                    "description": "OU created by AWS provisioner. " "OU creation",
                    "name": full_group_container_dn,
                },
            )
        else:
            logger.info(f"Entry OU={workspace_ou} exists")

        return ou_entry

    # Create new workspace groups if doesn't exist
    def create_groups(
        self,
        connection: Connection,
        workspace_name: str,
        ou_container_dn: str,
        group_object_class: str,
        roles: list,
        group_category: str,
        group_type: int,
        attributes: dict,
        sailpoint_enabled: bool = False,
        all_groups_dn: str = None
    ):
        workspace_short_name = utils.get_ws_shortname(workspace_name)
        workspace_ou = workspace_short_name.upper()

        # Create OU if it doesn't exist
        ou_entry = self.create_ws_ou(
            connection=connection,
            workspace_name=workspace_name,
            ou_container_dn=ou_container_dn,
        )
        logger.info(f"Workspace OU : {ou_entry} ")

        logger.info(
            f"Provisioning groups for workspace: {workspace_short_name} in OU: {workspace_ou}\n"
        )
        if group_type == utils.LOCAL_GROUP:
            group_name = f"SLG-{group_category}-{workspace_short_name}"
        elif group_type == utils.GLOBAL_GROUP:
            group_name = f"SGG-{group_category}-{workspace_short_name}"

        if group_category == utils.VIRTUAL_MACHINES and group_name.startswith('SGG'):
            vm_parent_dn = f"SLG-{group_category}-{workspace_short_name}"

        # workspace_group = f'SLG-VM-AWS-OCRemoteMgmt'
        full_group_container_dn = f"OU={workspace_ou},{ou_container_dn}"

        # Sort by name and create SLG VM group before SGG group
        sorted_roles=sorted(roles, key=lambda x: x.startswith('SLG'),reverse=True)
        for role in sorted_roles:
            # Add a group entry for the role
            role_name = f"{group_name}-{role}"
            role_dn = f"cn={role_name},{full_group_container_dn}"
            group_attributes = {
                "groupType": group_type,
                "name": role_name,
                "sAMAccountName": role_name,
                "displayName": role_name,
            }
            for name in attributes:
                if attributes[name] is not None:
                    group_attributes[name] = attributes[name]

            # Add an attribute for sailpoint enabled groups
            if sailpoint_enabled:
                group_attributes[utils.SAILPOINT_PROCESS_GROUP_ATTR_NAME] = (
                    utils.SAILPOINT_PROCESS_GROUP_ATTR_VALUE
                )

            # Add memberOf depending on group category
            if (group_category == utils.VIRTUAL_MACHINES and
                group_type == utils.GLOBAL_GROUP and vm_parent_dn):
                parent_dn = f"cn={vm_parent_dn}-{role},{full_group_container_dn}"
            else:
                parent_dn = all_groups_dn if (group_category == utils.WORKSPACES and
                                              group_type == utils.GLOBAL_GROUP) else None
                
            with connection:
                role_entry = utils.add_entry(
                    connection=connection,
                    dn=role_dn,
                    object_class=group_object_class,
                    attributes=group_attributes,
                    parent_dn=parent_dn
                )
                if not role_entry:
                    logger.info(f"Role group created:  {role_name}")
        logger.info(
            f"Finished provisioning groups for workspace: {workspace_short_name} \n"
        )

    def delete_groups(
        self, connection: Connection, workspace_name: str, ws_ou_container_dn: str
    ):
        workspace_ou = utils.get_ws_shortname(workspace_name).upper()
        workspace_ou_dn = f"OU={workspace_ou},{ws_ou_container_dn}"
        logger.info(f"Initiating recursive delete for {workspace_ou_dn}")
        utils.recursive_delete(connection, workspace_ou_dn)

    # Get groups of a workspace
    def get_groups(
        self,
        connection: Connection,
        workspace_name: str,
        ou_container_dn: str,
        group_object_class: str,
    ):

        workspace_short_name = utils.get_ws_shortname(workspace_name)
        workspace_ou = workspace_short_name.upper()
        workspace_ou_dn = f"OU={workspace_ou},{ou_container_dn}"
        logger.debug(f"Workspace OU: {workspace_ou_dn}")
        groups = []

        logger.info(
            f"Getting groups of workspace: {workspace_short_name} in OU: {workspace_ou}\n"
        )

        # Get group members of the workspace
        members = utils.get_members_of_object(
            connection=connection,
            object_dn=workspace_ou_dn,
            object_class=group_object_class,
        )
        for entry in members:
            groups.append(entry["dn"])

        return groups

    # Remove a particular group from AD
    def remove_group(
        self,
        connection: Connection,
        workspace_name: str,
        ou_container_dn: str,
        group_category: str,
        group_type: int,
        role_name: str,
    ):

        workspace_short_name = utils.get_ws_shortname(workspace_name)
        workspace_ou = workspace_short_name.upper()
        workspace_ou_dn = f"OU={workspace_ou},{ou_container_dn}"
        if group_type == utils.GLOBAL:
            role_dn = f"CN=SGG-{group_category}-{workspace_short_name}-{role_name},{workspace_ou_dn}"
        else:
            role_dn = f"CN=SLG-{group_category}-{workspace_short_name}-{role_name},{workspace_ou_dn}"
        print(role_dn)

        logger.info(f"Removing group: {role_dn}\n")

        # Delete group of the workspace
        utils.remove_entry(connection=connection, dn=role_dn, recursive=False)
