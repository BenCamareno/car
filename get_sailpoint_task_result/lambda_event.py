from typing import Dict
from common.configuration_data.base_configs import str2bool


class LambdaEventError(Exception):
    pass


class LambdaEvent:
    def __init__(self, event: Dict):
        self._event = event

    @property
    def task_result_id(self) -> str:
        try:
            sailpoint_task_result_id = self._event["role"]["sailpoint_launch_workflow"][
                "taskresult_id"
            ]
        except KeyError as e:
            raise LambdaEventError("Failed to find TaskResult ID in lambda event") from e
        else:
            if not isinstance(sailpoint_task_result_id, str) or sailpoint_task_result_id == "":
                raise LambdaEventError("TaskResult ID must be a non-empty string")
        return sailpoint_task_result_id

    @property
    def sailpoint_state_enabled(self) -> bool:
        try:
            base_config_data = self._event["base_configs"]["data"]
        except KeyError as e:
            raise LambdaEventError("Failed to find base_configs/data in lambda event") from e
        else:
            sailpoint_state_enabled = str2bool(base_config_data.get("sailpoint_state_enabled"))

        # Not specifying sailpoint_state_enabled flag means it's enabled (non-test scenario)
        if sailpoint_state_enabled is None:
            return True
        if not isinstance(sailpoint_state_enabled, bool):
            raise LambdaEventError("SailPoint Enabled flag must be a boolean")
        return sailpoint_state_enabled
