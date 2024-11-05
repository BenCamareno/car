def get_role_domains(roles_metadata):
    if roles_metadata is not None:
        ws_ad_domain_list = []
        vm_ad_domain_list = []
        for role in roles_metadata:
            role_type = str(role["role_type"]).lower()
            privileged_category = str(role["privileged_category"]).lower()
            if role_type == WS_ROLES_TYPE and privileged_category != ROLE_PRIVILEGED:
                try:
                    ws_ad_domain_list.append(role["ad_domain"])
                except KeyError as ex:
                    if (
                        role["privileged_category"] == "privileged"
                        and role["role_name"] == "Workspace Admin"
                    ):
                        continue
                    else:
                        logger.error(f"Missing ad_domain in {role}")
                        raise ex
            elif role_type == VM_ROLES_TYPE:
                try:
                    vm_ad_domain_list.append(role["ad_domain"])
                except KeyError as ex:
                    logger.error(f"Missing ad_domain in {role}")
                    raise ex
        if len(set(ws_ad_domain_list)) > 1 or len(set(vm_ad_domain_list)) > 1:
            logger.error(f"Mismatched domains in {roles_metadata}")
            raise ADGroupMismatchDomain
        return ws_ad_domain_list[0] if len(ws_ad_domain_list) > 0 else None, (
            vm_ad_domain_list[0] if len(vm_ad_domain_list) > 0 else None
        )
    else:
        return None, None
