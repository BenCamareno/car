import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as sfn from 'aws-cdk-lib/aws-stepfunctions'
import * as tasks from 'aws-cdk-lib/aws-stepfunctions-tasks'
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as path from 'path';
import { getSubnets, getSecurityGroups } from './common/vpc';
import { AwsIdentitySSOStack } from './sso-stack';
import { AwsIdentityPrivilegedSAStack } from './privileged_sa-stack';
import { ADGroupStack } from './ad-group-stack';
import { SailpointCyberarkStack } from './sailpoint-cyberark-stack';

export interface AwsIdentityCdkStackProps extends cdk.StackProps {
  lambdaExecutionRole: string, // Role to execute lambda function
  statemachineExecutionRole: string, // Role for statemachine
  nexusCallbackCrossAccountRole: string, // Role for cross-account callback to nexus orchestrator
  mgmtSubnets: ec2.SubnetAttributes[], // Subnets of Mgmt zone from 3 AZs
  mgmtSecurityGroup: string[], // Mgmt security group
  domainApiGatewayCidrs: string[],
  eventBusArn: string, // arn of the event bus,
  nexusIAMPrincipal: string, // iam principal of nexus that the resource policy of the event bus will allow
  githubEnterpriseCidrs: string[],
  source: string,
  release_channel: string[],
  service_tier: string[],
  stage: string
}

export class AwsIdentityCdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: AwsIdentityCdkStackProps) {
    super(scope, id, props);

    const OPERATION_CREATE = "create"
    const OPERATION_DELETE = "delete"
    const OPERATION_RETRIEVE = "retrieve"
    const OPERATION_ASSIGN = "assign"

    const DEPLOYMENT_STATUS_RUNNING = "running"
    const DEPLOYMENT_STATUS_SUCCESS = "success"
    const DEPLOYMENT_STATUS_FAILURE = "failure"

    // Get the CBA VPC
    const currentVpc = ec2.Vpc.fromLookup(this, 'vpc', {
      tags: { 'aws:cloudformation:logical-id': 'Vpc' },
    });

    const mgmtSubnetSelection = getSubnets(this, "IdentitySubnets", props.mgmtSubnets);

    // Create the GitHub security group
    const githubSecurityGroup = new ec2.SecurityGroup(this, "CBAGithubSecurityGroup", {
      vpc: currentVpc,
      description: "Allow egress access to CBA internal GitHub Enterprise",
      securityGroupName: `CBAGithubSecurityGroup${props.stage}`,
      allowAllOutbound: false
    });
    props.githubEnterpriseCidrs.forEach((githubIP) => {
      githubSecurityGroup.addEgressRule(ec2.Peer.ipv4(githubIP), ec2.Port.tcp(443), 'CBA GitHub Enterprise');
    });
    props.mgmtSecurityGroup.push(githubSecurityGroup.securityGroupId);

    // Fetch CBA Security Groups
    const mgmtSecurityGroups = getSecurityGroups(this, "IdentitySecGroupsMgmt", props.mgmtSecurityGroup)

    // Set proxy variable to be used in lambda function
    const proxyConfig = 'http://app-proxy:3128';
    const noProxyConfig =
      '169.254.170.3, 169.254.170.2, 169.254.169.254, localhost, 127.0.0.1, s3.ap-southeast-2.amazonaws.com, s3-ap-southeast-2.amazonaws.com, dynamodb.ap-southeast-2.amazonaws.com, .aws.prod.au.internal.cba, .aws.dev.au.internal.cba, .aws.test.au.internal.cba, .aws.beta.au.internal.cba, github.source.internal.cba';

    // Docker image used to build and bundle python dependencies for functions and layers
    const pythonRuntimeDockerImage = "hub.docker.internal.cba/sam/build-python3.11:latest-x86_64"

    // Get the lambda role
    const lambdaExecutionRole = iam.Role.fromRoleArn(
      this,
      'IdentityLambdaExecutionRole',
      props.lambdaExecutionRole,
      {
        mutable: false
      }
    );

    // Get the state machine execution role
    const statemachineExecutionRole = iam.Role.fromRoleArn(
      this,
      'IdentityStateMachineExecutionRole',
      props.statemachineExecutionRole,
      {
        mutable: false
      }
    );

    // Get the nexus callback cross-account role
    const nexusCallbackRole = iam.Role.fromRoleArn(this, 'NexusCallbackCrossAccountRole',
      props.nexusCallbackCrossAccountRole,
      {
        mutable: false
      }
    );
    const callbackTaskRole = sfn.TaskRole.fromRole(nexusCallbackRole);

    // Create a common lambda layer
    const commonFnLayer = new lambda.LayerVersion(this, "IdentityCdkCommonLayer", {
      code: lambda.Code.fromAsset(path.join(__dirname, `../lambdas/layers/common`), {
        bundling: {
          image: cdk.DockerImage.fromRegistry(pythonRuntimeDockerImage),
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output/python && cp -au . /asset-output/python/common'
          ],
        },
      }),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      compatibleArchitectures: [lambda.Architecture.X86_64]
    });

    const githubIntegrationFnLayer = new lambda.LayerVersion(this, "githubIntegrationFnLayer", {
      code: lambda.Code.fromAsset(path.join(__dirname, `../lambdas/layers/github_integration`)),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      description: 'Github Integration Layer',
    });

    const adgroupstack = new ADGroupStack(this, 'ADGroupStack', {
      lambdaExecutionRole: props.lambdaExecutionRole,
      currentVpc: currentVpc,
      mgmtSecurityGroups: mgmtSecurityGroups,
      mgmtSubnetSelection: mgmtSubnetSelection,
      lambdaLayers: [commonFnLayer]
    });

    const ssoStack = new AwsIdentitySSOStack(this, 'AwsIdentitySSOStack', {
      lambdaExecutionRole: props.lambdaExecutionRole,
      currentVpc: currentVpc,
      mgmtSecurityGroups: mgmtSecurityGroups,
      mgmtSubnetSelection: mgmtSubnetSelection,
      lambdaLayers: [commonFnLayer]
    });

    const sailpointCyberarkStack = new SailpointCyberarkStack(this, 'SailpointCyberarkStack', {
      stage: props.stage,
      lambdaExecutionRole: lambdaExecutionRole,
      vpc: currentVpc,
      mgmtSubnetSelection: mgmtSubnetSelection,
      mgmtSecurityGroups: mgmtSecurityGroups,
      domainApiGatewayCidrs: props.domainApiGatewayCidrs,
      commonLambdaLayer: commonFnLayer,
      pythonRuntimeDockerImage: pythonRuntimeDockerImage,
      proxyConfig: proxyConfig,
      noProxyConfig: noProxyConfig
    });

    const workspaceRoleMetadataFn = new lambda.Function(this, "workspaceRoleMetadataFn", {
      functionName: `workspaceRoleMetadataFn${props.stage}`,
      role: lambdaExecutionRole,
      description: 'Nexus Workspace Role Metadata function',
      handler: 'handler.lambda_handler',
      runtime: lambda.Runtime.PYTHON_3_11,
      memorySize: 512,
      timeout: cdk.Duration.minutes(10),
      layers: [commonFnLayer, githubIntegrationFnLayer],
      code: lambda.Code.fromAsset(path.join(__dirname, `../lambdas/workspace_role_metadata`)),
      architecture: lambda.Architecture.X86_64,
      environment: {
        HTTP_PROXY: proxyConfig,
        HTTPS_PROXY: proxyConfig,
        NO_PROXY: noProxyConfig
      },
      vpc: currentVpc,
      securityGroups: mgmtSecurityGroups,
      vpcSubnets: mgmtSubnetSelection
    });

    const updateNexusDeploymentStatusFn = new lambda.Function(this, "UpdateNexusDeploymentStatus", {
      role: lambdaExecutionRole,
      description: 'Updates Nexus Metadata with deployment status of identity pipeline',
      handler: 'main.lambda_handler',
      runtime: lambda.Runtime.PYTHON_3_11,
      memorySize: 512,
      timeout: cdk.Duration.minutes(10),
      layers: [commonFnLayer],
      code: lambda.Code.fromAsset(path.join(__dirname, `../lambdas/update_nexus_deployment_status`)),
      architecture: lambda.Architecture.X86_64,
      environment: {
        HTTP_PROXY: proxyConfig,
        HTTPS_PROXY: proxyConfig,
        NO_PROXY: noProxyConfig
      },
      vpc: currentVpc,
      securityGroups: mgmtSecurityGroups,
      vpcSubnets: mgmtSubnetSelection
    });

    // Handling success
    const success = new sfn.Succeed(this, 'Success');
    const sendTaskSuccessToNexus = new tasks.CallAwsService(this, 'Send task success', {
      service: 'sfn',
      action: 'sendTaskSuccess',
      credentials: {
        role: callbackTaskRole
      },
      iamResources: ['*'],  // not effective as role is mutable. Just added to prevent error.
      parameters: {
        "Output": sfn.JsonPath.format(
          "\"Successfully executed {} for account {} #{}.\"",
          sfn.JsonPath.stringAt("$.detail.deployment_module"), sfn.JsonPath.stringAt("$.detail.target_workspace_name"), sfn.JsonPath.stringAt("$.detail.target_account_id")),
        "TaskToken.$": "$.detail.callback_task_token"
      },
    })
    const updateNexusDeploymentStatusSuccess = new tasks.LambdaInvoke(this, "Put Success Nexus deployment status", {
      lambdaFunction: updateNexusDeploymentStatusFn,
      payload: sfn.TaskInput.fromObject({
        "deployment_status": DEPLOYMENT_STATUS_SUCCESS,
        "detail-type.$": "$.detail-type",
        "detail.$": "$.detail",
      }),
      resultPath: sfn.JsonPath.DISCARD
    })

    const notifySuccessToNexus = updateNexusDeploymentStatusSuccess
      .next(sendTaskSuccessToNexus)
      .next(success)

    // Handling failures
    const failure = new sfn.Fail(this, 'Failure');
    const sendTaskFailureToNexus = new tasks.CallAwsService(this, 'Send task failure', {
      service: 'sfn',
      action: 'sendTaskFailure',
      credentials: {
        role: callbackTaskRole
      },
      iamResources: ['*'],  // not effective as role is mutable. Just added to prevent error.
      parameters: {
        "Cause.$": "$.error_output.Cause",
        "Error.$": "$.error_output.Error",
        "TaskToken.$": "$.detail.callback_task_token"
      },
    })
    const updateNexusDeploymentStatusFailure = new tasks.LambdaInvoke(this, "Put Failure Nexus deployment status", {
      lambdaFunction: updateNexusDeploymentStatusFn,
      payload: sfn.TaskInput.fromObject({
        "deployment_status": DEPLOYMENT_STATUS_FAILURE,
        "detail-type.$": "$.detail-type",
        "detail.$": "$.detail",
      }),
      resultPath: sfn.JsonPath.DISCARD
    })

    const notifyFailureToNexus = updateNexusDeploymentStatusFailure
      .next(sendTaskFailureToNexus)
      .next(failure)

    // Final choices for handling success and failure
    const customTriggerChoiceSuccess = new sfn.Choice(this, "Notify success to Nexus?")
      .when(sfn.Condition.and(
        sfn.Condition.stringEquals("$.detail.deployment_module", "identity_access"),
        sfn.Condition.isPresent("$.detail.callback_task_token")
      ), notifySuccessToNexus)
      .otherwise(success)
    const customTriggerChoiceFailure = new sfn.Choice(this, "Notify failure to Nexus?")
      .when(sfn.Condition.and(
        sfn.Condition.stringEquals("$.detail.deployment_module", "identity_access"),
        sfn.Condition.isPresent("$.detail.callback_task_token")
      ), notifyFailureToNexus)
      .otherwise(failure)

    // Update Nexus metadata with deployment status: running
    const updateNexusDeploymentStatusRunning = new tasks.LambdaInvoke(this, "Put Running Nexus deployment status", {
      lambdaFunction: updateNexusDeploymentStatusFn,
      payload: sfn.TaskInput.fromObject({
        "deployment_status": DEPLOYMENT_STATUS_RUNNING,
        "detail-type.$": "$.detail-type",
        "detail.$": "$.detail",
      }),
      resultPath: sfn.JsonPath.DISCARD
    }).addCatch(customTriggerChoiceFailure, {
      resultPath: "$.error_output"
    })

    const getParameters = new tasks.CallAwsService(this, "Get base configs", {
      service: "ssm",
      action: "getParameter",
      parameters: {
        "Name": "/CNS/identitystatemachine/base_configs"
      },
      resultSelector: {
        "data.$": "States.StringToJson($.Parameter.Value)"
      },
      resultPath: "$.base_configs",
      iamResources: ['*'],  // not effective as role is mutable. Just added to prevent error.
    }).addCatch(customTriggerChoiceFailure, {
      resultPath: "$.error_output"
    });

    // Note: Overwrites the data from the task above
    const taskWorkspaceMetadata = new tasks.LambdaInvoke(this, "Retrieve workspace & role metadata", {
      lambdaFunction: workspaceRoleMetadataFn,
      resultSelector: {
        "roles_metadata.$": "$.Payload.roles_metadata",
        "workspace_metadata.$": "$.Payload.workspace_metadata"
      },
      resultPath: "$.metadata",
    }).addCatch(customTriggerChoiceFailure, {
      resultPath: "$.error_output"
    })

    /// Create AD group
    const createADgroup = new tasks.LambdaInvoke(this, "Create AD group in CBAiNet", {
      lambdaFunction: adgroupstack.getADGroupFunction(),
      payload: sfn.TaskInput.fromObject({
        "operation": OPERATION_CREATE,
        "workspace_metadata.$": "$.metadata.workspace_metadata",
        "roles_metadata.$": "$.metadata.roles_metadata",
        "base_configs.$": "$.base_configs"
      }),
      resultPath: sfn.JsonPath.DISCARD
    }).addRetry({
      errors: ["ADGroupCreationorDeletionNon200ResponseError", "HTTPError", "ConnectionError", "Timeout"],
      interval: cdk.Duration.seconds(120),
      maxAttempts: 30,
      backoffRate: 1
    }).addCatch(customTriggerChoiceFailure, {
      resultPath: "$.error_output"
    })

    /// This defines the Map state of the Role Iterator
    const roleIteratorOnboarding = new sfn.Map(this, "Role Iterator Onboarding", {
      maxConcurrency: 10,
      itemsPath: '$.metadata.roles_metadata',
      itemSelector: {
        "workspace_metadata.$": "$.metadata.workspace_metadata",
        "base_configs.$": "$.base_configs",
        'role.$': '$$.Map.Item.Value'
      },
      resultPath: '$.role_iterator_output'
    });

    /// This defines the Map state of the Role Iterator
    const roleIteratorOffboarding = new sfn.Map(this, "Role Iterator Offboarding", {
      maxConcurrency: 10,
      itemsPath: '$.metadata.roles_metadata',
      itemSelector: {
        "workspace_metadata.$": "$.metadata.workspace_metadata",
        "base_configs.$": "$.base_configs",
        'role.$': '$$.Map.Item.Value'
      },
      resultPath: '$.role_iterator_output'
    });

    const iteratorFail = new sfn.Fail(this, "Iterator failure", {
      causePath: '$.error_output.Cause',
      errorPath: '$.error_output.Error'
    });

    const getADgroup = new tasks.LambdaInvoke(this, "Retrieve AD group details", {
      lambdaFunction: adgroupstack.getADGroupFunction(),
      payload: sfn.TaskInput.fromObject({
        "operation": OPERATION_RETRIEVE,
        "role.$": "$.role",
        "workspace_metadata.$": "$.workspace_metadata",
        "base_configs.$": "$.base_configs"
      }),
      resultSelector: {
        "ad_group_name.$": "$.Payload.ad_group_name",
        "ad_group_full_dn_name.$": "$.Payload.ad_group_full_dn_name"
      },
      resultPath: '$.role.ad_group_config'
    }).addRetry({
      errors: ["ADGroupGetNon200ResponseError", "ADGroupNotFoundError", "HTTPError", "ConnectionError", "Timeout"],
      interval: cdk.Duration.seconds(120),
      maxAttempts: 30
    }).addCatch(iteratorFail, {
      resultPath: '$.error_output'
    })

    const checkRolePrivileged = new sfn.Choice(this, "Privilege category check");
    const nonPrivilegedCondition = sfn.Condition.stringEquals('$.role.privileged_category', "non-privileged");
    const privilegedCondition = sfn.Condition.stringEquals('$.role.privileged_category', "privileged")
    const vmCondition = sfn.Condition.stringEquals('$.role.role_type', "VM");
    const wsCondition = sfn.Condition.stringEquals('$.role.role_type', "WS");
    const nonPrivilegedWSCondition = sfn.Condition.and(nonPrivilegedCondition, wsCondition)
    const privilegedVMCondition = sfn.Condition.and(privilegedCondition, vmCondition)
    const privilegedWSCondition = sfn.Condition.and(privilegedCondition, wsCondition)

    const checkPermissionSet = new sfn.Choice(this, "Check if permissionset?");
    const permissionSetPresent = sfn.Condition.isPresent('$.role.permission_set_name');
    const permissionSetAbsent = new sfn.Pass(this, 'Skip permissionset assignment');

    const ssoGetGroup = new tasks.LambdaInvoke(this, "Get group from IdentityStore", {
      lambdaFunction: ssoStack.getSSOGetGroupFunction(),
      payload: sfn.TaskInput.fromObject({
        "sso_state_enabled.$": "$.base_configs.data.sso_state_enabled",
        "identity_store_id.$": "$.base_configs.data.sso_state_configs.identity_store_id",
        "ad_group_name.$": "$.role.ad_group_config.ad_group_name"
      }),
      resultSelector: {
        "identitystore_group_id.$": "$.Payload.identitystore_group_id"
      },
      resultPath: '$.role.identitystore_group_id'
    }).addRetry({
      errors: ["ThrottlingException", "CredentialRetrievalError", "ConnectTimeoutError", "GroupNotFoundException"],
      interval: cdk.Duration.seconds(120),
      maxAttempts: 62,
      backoffRate: 1,
    }).addCatch(iteratorFail, {
      resultPath: '$.error_output'
    });

    const assignPermissionSet = new tasks.LambdaInvoke(this, "Assign SSO Permissionset", {
      lambdaFunction: ssoStack.getSSOPermissionAssignerFunction(),
      payload: sfn.TaskInput.fromObject({
        "sso_state_enabled.$": "$.base_configs.data.sso_state_enabled",
        "identity_store_id.$": "$.base_configs.data.sso_state_configs.identity_store_id",
        "sso_instance_arn.$": "$.base_configs.data.sso_state_configs.sso_instance_arn",
        "operation": OPERATION_ASSIGN,
        "ad_group_name.$": "$.role.ad_group_config.ad_group_name",
        "permissionset_name.$": "$.role.permission_set_name",
        "target_account_id.$": "$.workspace_metadata.response_elements[0].account_id"
      }),
      resultSelector: {
        "ps_assignment_status.$": "$.Payload.message"
      },
      resultPath: '$.role.ps_assignment_status'
    }).addRetry({
      errors: ["ThrottlingException", "CredentialRetrievalError", "ConnectTimeoutError"],
      interval: cdk.Duration.seconds(120),
      maxAttempts: 18,
      backoffRate: 1
    }).addCatch(iteratorFail, {
      resultPath: '$.error_output'
    });

    const powershellLayer = new lambda.LayerVersion(this, "powershellLayer", {
      code: lambda.Code.fromAsset("PwshRuntimeLayer.zip"),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_11],
      compatibleArchitectures: [lambda.Architecture.X86_64]
    });

    const privilegedSAStack = new AwsIdentityPrivilegedSAStack(this, 'AwsIdentityPrivilegedSAStack', {
      lambdaExecutionRole: props.lambdaExecutionRole,
      lambdaLayers: [commonFnLayer, githubIntegrationFnLayer, powershellLayer],
      architecture: lambda.Architecture.X86_64,
      environment: {
        HTTP_PROXY: proxyConfig,
        HTTPS_PROXY: proxyConfig,
        NO_PROXY: noProxyConfig
      },
      vpc: currentVpc,
      securityGroups: mgmtSecurityGroups,
      vpcSubnets: mgmtSubnetSelection
    });

    const createIAMResource = new tasks.LambdaInvoke(this, "Setup IAM entities", {
      lambdaFunction: privilegedSAStack.getPrivilegedSAFunction(),
      payload: sfn.TaskInput.fromObject({
        "operation": OPERATION_CREATE,
        "role_name.$": "$.role.iam_role_name",
        "aws_account_id.$": "$.workspace_metadata.response_elements[0].account_id",
        "ci_number.$": "$.workspace_metadata.response_elements[0].ci_number",
        "base_configs.$": "$.base_configs"
      }),
      resultSelector: {
        "iam_user_name.$": "$.Payload.iam_user_name",
        "access_key_id.$": "$.Payload.access_key_id",
        "encrypted_credentials.$": "$.Payload.encrypted_credentials",
        "role_arn.$": "$.Payload.role_arn"
      },
      resultPath: "$.iam_details"
    }).addRetry({
      errors: ["ValidateCfnTemplateError", "CfnStackOperationError", "AccessKeyError"],
      interval: cdk.Duration.seconds(300),
      maxAttempts: 3
    }).addCatch(iteratorFail, {
      resultPath: '$.error_output',
    });

    const createVMIdentityResource = new sfn.Pass(this, "Setup VM identities", {
      result: sfn.Result.fromString('VM resource created'),
      resultPath: '$.role.vm_resource_status'
    });

    const apiStatusRetryPlacholder = new sfn.Pass(this, "Call API status retry<TBA>", {
      outputPath: '$.role'
    });

    const iteratorChoiceFailPass = new sfn.Pass(this, "Unhandled choice", {
      resultPath: '$.error_output',
      result: sfn.Result.fromObject({
        cause: "Choice state failure due to no matching choice",
        error: '400'
      })
    });

    const launchWorkflowSailpointState = new tasks.LambdaInvoke(this, "Launch Sailpoint workflow", {
      lambdaFunction: sailpointCyberarkStack.launchSailpointWorkflowFunction,
      payload: sfn.TaskInput.fromObject({
        "role_name.$": "$.role.role_name",
        "sailpoint_state_enabled.$": "$.base_configs.data.sailpoint_state_enabled",
        "role_type.$": "$.role.role_type",
        "ad_group_suffix.$": "$.role.ad_group_suffix",
        "workspace_metadata.$": "$.workspace_metadata",
        "secret_name_cbainet_configs": "/CNS/identitystatemachine/cbainet_configs",
        "secret_name_cert_configs": "/CNS/identitystatemachine/certificates",
        "role.$": "$.role"
      }),
      resultSelector: {
        "taskresult_id.$": "$.Payload.sailpoint_taskresult_id"
      },
      resultPath: '$.role.sailpoint_launch_workflow'
    }).addRetry({
      errors: ["WorkflowFailedWithNoTaskIdInResponseError"],
      interval: cdk.Duration.seconds(120),
      maxAttempts: 5,
      backoffRate: 1,
    }).addCatch(iteratorFail, {
      resultPath: '$.error_output',
    });

    const waitBeforeRelaunchWorkflowSailpoint = new sfn.Wait(this, 'Wait Before Relaunch workflow', {
      time: sfn.WaitTime.duration(cdk.Duration.seconds(120))
    }).next(launchWorkflowSailpointState);

    const taskGetSailpointTaskResult = new tasks.LambdaInvoke(this, "Get Sailpoint TaskResult", {
      lambdaFunction: sailpointCyberarkStack.getSailpointTaskResultFunction,
      resultSelector: {
        'role_onboarding_status.$': '$.Payload.role_onboarding_status'
      },
      resultPath: '$.role.sailpoint_task_result'
    }).addRetry({
      errors: ["OnboardingTaskNotCompleted"],
      interval: cdk.Duration.minutes(10),
      maxAttempts: 5,
      maxDelay: cdk.Duration.minutes(10)
    }).addCatch(waitBeforeRelaunchWorkflowSailpoint, {
      errors: ["TaskResultNotFoundError"],
      resultPath: sfn.JsonPath.DISCARD,
    }).addCatch(iteratorFail, {
      errors: ["States.TaskFailed", "NonRetriableError", "OnboardingTaskFailed"],
      resultPath: '$.error_output',
    }).addCatch(iteratorFail, {
      resultPath: '$.error_output',
    });

    const mapCatchProps: sfn.CatchProps = {
      errors: [sfn.Errors.ALL],
      resultPath: '$.error_output'
    };
    const launchWorkflowCyberarkState = new tasks.LambdaInvoke(this, "Launch CyberArk workflow", {
      lambdaFunction: sailpointCyberarkStack.launchCyberarkWorkflowLambda,
      payload: sfn.TaskInput.fromObject({
        "role_name.$": "$.role.role_name",
        "cyberark_state_enabled.$": "$.base_configs.data.cyberark_state_enabled",
        "role_type.$": "$.role.role_type",
        "workspace_metadata.$": "$.workspace_metadata",
        "secret_name_cbainet_configs": "/CNS/identitystatemachine/cbainet_configs",
        "secret_name_cert_configs": "/CNS/identitystatemachine/certificates",
        "role.$": "$.role",
        "iam_details.$": "$.iam_details" 
      }),
      resultSelector: {
        "cyberark_taskresult_id.$": "$.Payload.cyberark_taskresult_id"

      },
      resultPath: '$.role.cyberark_taskresult_id'
    }).addCatch(iteratorFail, {
      resultPath: '$.error_output',
    })

    const waitBeforeRelaunchWorkflowCyberArk = new sfn.Wait(this, 'Wait Before Relaunch CyberArk workflow', {
      time: sfn.WaitTime.duration(cdk.Duration.seconds(120))
    }).next(launchWorkflowCyberarkState);

    const getCyberArkResult = new tasks.LambdaInvoke(this, "Get CyberArk Workflow Result", {
      lambdaFunction: sailpointCyberarkStack.getCyberarkWorkflowResultFunction,
      resultSelector: {
        'role_onboarding_status.$': '$.Payload.role_onboarding_status'
      },
      resultPath: '$.role.cyberark_task_result'
    }).addRetry({
      errors: ["OnboardingTaskNotCompleted"],
      interval: cdk.Duration.minutes(30),
      maxAttempts: 10,
      backoffRate: 1,
      maxDelay: cdk.Duration.minutes(30)
    }).addCatch(waitBeforeRelaunchWorkflowCyberArk, {
      errors: ["TaskResultNotFoundError"],
      resultPath: sfn.JsonPath.DISCARD,
    }).addCatch(iteratorFail, {
      errors: ["States.TaskFailed", "NonRetriableError", "OnboardingTaskFailed"],
      resultPath: '$.error_output',
    }).addCatch(iteratorFail, {
      resultPath: '$.error_output',
    });

    const sailpointOnboarding = launchWorkflowSailpointState.next(taskGetSailpointTaskResult);
    const cyberArkOnboarding = launchWorkflowCyberarkState.next(getCyberArkResult);

    /// Role iterator definition below, it describes how the state machines flows within the iterator
    const roleIteratorForOnboardingDef = getADgroup
      .next(checkRolePrivileged
        .when(nonPrivilegedWSCondition, ssoGetGroup
          .next(checkPermissionSet
            .when(permissionSetPresent, assignPermissionSet.next(sailpointOnboarding))
            .otherwise(permissionSetAbsent.next(sailpointOnboarding)))
        )
        .when(privilegedWSCondition, createIAMResource.next(cyberArkOnboarding))
        .when(privilegedVMCondition, createVMIdentityResource.next(cyberArkOnboarding))
        .otherwise(iteratorChoiceFailPass
          .next(iteratorFail)
        )
      );

    // Role iterator for role offboarding
    const roleIteratorForOffboardingDef = new sfn.Pass(this, "Offboard roles from CyberArk")
      .next(new sfn.Pass(this, "Offboard roles from Sailpoint"))
      .next(new sfn.Pass(this, "Delete IAM entities"))
      .next(new sfn.Pass(this, "Delete AD group from CBAiNet"))

    // Check for execution type
    const choiceExecutionType = new sfn.Choice(this, "Onboarding OR Offboarding?")
      .when(sfn.Condition.stringEquals("$.detail-type", "resource_creation_update"), createADgroup.next(roleIteratorOnboarding.next(customTriggerChoiceSuccess)))
      .when(sfn.Condition.stringEquals("$.detail-type", "resource_deletion"), roleIteratorOffboarding.next(customTriggerChoiceSuccess))

    // Adding role onboarding definition to iterator
    roleIteratorOnboarding.itemProcessor(roleIteratorForOnboardingDef);
    roleIteratorOnboarding.addCatch(customTriggerChoiceFailure, mapCatchProps)

    // Add role offboarding definition to iterator
    roleIteratorOffboarding.itemProcessor(roleIteratorForOffboardingDef);
    roleIteratorOffboarding.addCatch(customTriggerChoiceFailure, mapCatchProps)

    /// This defines the flow of the overall state machine for role onboarding
    const definition = updateNexusDeploymentStatusRunning
      .next(getParameters)
      .next(taskWorkspaceMetadata)
      .next(choiceExecutionType)

    /// Overall State Machine definition
    const identityStateMachine = new sfn.StateMachine(this, 'IdentityStateMachine', {
      stateMachineName: `IdentityStatemachine${props.stage}`,
      role: statemachineExecutionRole,
      definitionBody: sfn.DefinitionBody.fromChainable(definition),
      // The timeout is set based on nexus orchestrator timeout. Only change it considering nexus time out as well.
      timeout: cdk.Duration.minutes(190),
      comment: 'Statemachine for identity & role onboarding',
    });

    // allow nexus to put events to the default event bus via adding to the resource policy
    const eventBusPolicy = new events.CfnEventBusPolicy(this, `DefaultEventBusPolicy${props.stage}`, {
      statementId: `AllowAccountToPutEvents${props.stage}`,
      eventBusName: "default",
      statement: {
        "Effect": "Allow",
        "Principal": { "AWS": props.nexusIAMPrincipal },
        "Action": "events:PutEvents",
        "Resource": props.eventBusArn
      },
    });

    //get default event bus
    const eventBus = events.EventBus.fromEventBusAttributes(this, `DefaultEventBus${props.stage}`, {
      eventBusName: "default", eventBusPolicy: eventBusPolicy.statement,
      eventBusArn: props.eventBusArn
    });

    //add the state machine to the event rule target
    const eventRuleTarget = new targets.SfnStateMachine(identityStateMachine, {
      role: statemachineExecutionRole
    });

    //create event rule
    const rule = new events.Rule(this, `IdentityStatemachineEventsRule${props.stage}`, {
      eventPattern: {
        source: [props.source],
        detailType: ["resource_creation_update", "resource_deletion"],
        detail: {
          release_channel: props.release_channel,
          service_tier: props.service_tier,
          deployment_module: ["identity_access", "identity_custom"]
        }
      },
      eventBus: eventBus,
      ruleName: `IdentityStatemachineEventsRule${props.stage}`,
      description: "Event Rule to trigger identity statemachine",
      targets: [
        eventRuleTarget
      ]
    });
  }
}
