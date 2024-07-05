
"""
Module which orchestrates the CyberArk API calls via the Domain APi Gateway (DAG)

Details:

cyberark_call: Function to make the CyberArk  APIs using the tokens fetched from the above function
                Group IDP access token

"""

import logging
import os
import requests
import tempfile
from common_sailpoint_cyberark.log_utils import log_http_request_details, log_http_response_details
logger = logging.getLogger()



class CyberArkApiError(Exception):
    pass


class CyberArkApiHttpAuthError(CyberArkApiError):
    pass


class CyberArkApiHttpNotFoundError(CyberArkApiError):
    pass


class CyberArkApiHttpOtherError(CyberArkApiError):
    pass


class CyberArkApiNonHttpRequestsError(CyberArkApiError):
    pass


class CyberArkApiInvalidResponseError(CyberArkApiError):
    pass


class CyberArkApiUnknownError(CyberArkApiError):
    pass



# TODO Modify this function and make it like CyberArk api call function
def call_cyberark_api(
        url, gidp_token, method, payload, client_public_cert_path, client_private_key_content,
        ca_cert_path,
        log_details=False
):
    """
    Calls one of the CyberArk endpoints as exposed via the Domain API Gateway (DAG)

    url: the CyberArk url you would like to call (exposed through DAG)
    dag_token: your DAG access token (obtained via GetBearerToken function above)
    method: what type of request you are making to CyberArk (GET, POST, PUT, so on)
    client_cert_path: path to your public certificate
    client_key_path: path to your private key
    data: (optional) data to send in your request, eg if you are making a POST request
    """
    headers = {
        "Authorization": f"Bearer {gidp_token}",
        "Accept": "application/json",
    }
    try:
        if log_details:
            log_http_request_details(method=method, url=url, payload=payload)
        with tempfile.NamedTemporaryFile(mode="w+") as client_private_key_temp_file:
            client_private_key_temp_file.write(client_private_key_content)
            client_private_key_temp_file.seek(0)
            response = requests.request(
                method,
                url,
                headers=headers,
                json=payload,
                cert=(client_public_cert_path, client_private_key_temp_file.name),
                verify=ca_cert_path,
            )
        if log_details:
            log_http_response_details(response)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as http_err:
        # Handle HTTP errors (e.g., authentication failure, not found)
        if response.status_code == 401:
            err_msg = f"401 Unautorised! Please retry in case the group IDP access token or CyberArk access token have expired."
            logger.exception(err_msg)
            raise CyberArkApiHttpAuthError(err_msg) from http_err
        elif response.status_code == 403:
            err_msg = f"403 Forbidden access! Please check if scope & clientID information is correct and has access to the CyberArk API.\n If the above information is correct, please retry in case the group IDP access token or CyberArk access token have expired."
            logger.exception(err_msg)
            raise CyberArkApiHttpAuthError(err_msg) from http_err
        elif response.status_code == 404:
            err_msg = f"404 Not found! Please check if ID is correct."
            logger.exception(err_msg)
            raise CyberArkApiHttpNotFoundError(err_msg) from http_err
        else:
            err_msg = f"HTTP error occurred while connecting to CyberArk IDP - {url}. HTTP status code received is {response.status_code}: {response.reason}"
            logger.exception(err_msg)
            raise CyberArkApiHttpOtherError(err_msg)
    except requests.exceptions.RequestException as req_err:
        # Handle other requests-related errors (e.g., connection issues)
        err_msg = f"Error communicating with CyberArk API - {url} via DAG!\n Details are: {req_err}"
        logger.exception(err_msg)
        raise CyberArkApiNonHttpRequestsError(err_msg) from req_err
    except (ValueError, Exception) as err:
        # Handle value error & other exceptions
        err_msg = f"Error while calling CyberArk API. Error: {err}"
        logger.exception(err_msg)
        raise CyberArkApiUnknownError(err_msg) from err
