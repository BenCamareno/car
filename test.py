import time
import boto3
#Replace with Session Name
#session = boto3.Session(profile_name='default')
assignment_detail = []
#Replace INSTANCE ARN
instance_arn = 'arn:aws:sso:::instance/ssoins-11111111111111111'
#Replace All PermissionSet ARNS for Unassignment
ps_arn=['arn:aws:sso:::permissionSet/ssoins-11111111111111111/ps-11111111111111111',
        'arn:aws:sso:::permissionSet/ssoins-11111111111111111/ps-11111111111111111',
        'arn:aws:sso:::permissionSet/ssoins-11111111111111111/ps-11111111111111111']

class assignment_info:
    def __init__(self,id,permset_arn,principaltype,principalid):
        self.id = id
        self.permset_arn=permset_arn
        self.principaltype=principaltype
        self.principalid=principalid

def listaccounts(permset_arn):
    client = boto3.client('sso-admin')
    accounts=[]
    paginator = client.get_paginator('list_accounts_for_provisioned_permission_set')
    response_iterator = paginator.paginate(
            InstanceArn=instance_arn,
            PermissionSetArn=permset_arn
    )
    for page in response_iterator:
        print (page['AccountIds'])
        for item in page['AccountIds']:
            accounts.append(item)
    #print (accounts)
    return accounts


def list_assign(account,permset_arn):
    client = boto3.client('sso-admin')
    paginator = client.get_paginator('list_account_assignments')
    #print(account)
    response_iterator = paginator.paginate(
        InstanceArn=instance_arn,
        AccountId=account,
        PermissionSetArn=permset_arn
        )

    for page in response_iterator:
        #print(page)
        for assignment in page['AccountAssignments']:
            assignment_detail.append (
                assignment_info(
                    assignment ['AccountId'],
                    assignment ['PermissionSetArn'],
                    assignment ['PrincipalType'],
                    assignment ['PrincipalId']
                )
            )

    #print (assignment_detail[0].id,assignment_detail[0].principaltype,assignment_detail[0].principalid)

    return assignment_detail


def unassignment():
    client = boto3.client('sso-admin')
    # Grab The Permission Set ARNs and replace permsets_arns list
    permsets_arns = ps_arn

    for permsets in permsets_arns:
        accounts = listaccounts(permsets)
        for accountno in accounts:
            assignments = list_assign(accountno,permsets)
            print(assignments)
            for sub in assignments:
                response = client.delete_account_assignment(
                            InstanceArn = instance_arn,
                            TargetId = sub.id,
                            TargetType = 'AWS_ACCOUNT',
                            PermissionSetArn = sub.permset_arn,
                            PrincipalType = sub.principaltype,
                            PrincipalId = sub.principalid
                        )
                request_id = response['AccountAssignmentDeletionStatus']['RequestId']
                max_retries = 2
                retry_ctr = 0
                try:
                    while (response['AccountAssignmentDeletionStatus']['Status']=='IN_PROGRESS' and retry_ctr<max_retries):
                        time.sleep((2^retry_ctr)*0.1)
                        response = client.describe_account_assignment_deletion_status(InstanceArn=instance_arn,AccountAssignmentDeletionRequestId=request_id)
                        print(response['AccountAssignmentDeletionStatus']['Status'])
                        print(retry_ctr)
                        print("in the while loop")
                        retry_ctr+=1
                    else:
                        if (response['AccountAssignmentDeletionStatus']['Status']=='SUCCEEDED'):
                            print("next record")
                        elif (response['AccountAssignmentDeletionStatus']['Status']=='FAILED'):
                            print ("failed")
                        else:
                            print ("statusCode:501, body:unknown")
                except Exception as e:
                    print(e)
    

unassignment()
