'''Upload a json manifest to Amazon s3.'''
import boto3
from botocore.exceptions import ClientError, ParamValidationError
from typing import Any

from mut.AuthenticationInfo import AuthenticationInfo
from mut.index.utils.AwaitResponse import wait_for_response
from mut.index.utils.Logger import log_unsuccessful


def _connect_to_s3() -> Any:
    authentication_info = AuthenticationInfo.load()
    session = boto3.session.Session(
        aws_access_key_id=authentication_info.access_key,
        aws_secret_access_key=authentication_info.secret_key)

    try:
        s3 = wait_for_response(
            'Opening connection to s3',
            lambda: session.resource('s3')
        )
        return s3
    except ClientError as ex:
        message = 'Unable to connect to s3.'
        log_unsuccessful('connection', message, ex)


def _upload(s3, bucket: str, key: str, manifest: str) -> None:
    try:
        wait_for_response(
            'Attempting to upload to s3 with key: ' + key,
            lambda: s3.Bucket(bucket).put_object(
                Key=key, Body=manifest, ContentType='application/json')
        )
        success_message = ('Successfully uploaded manifest '
                           'to {0} as {1}').format(bucket, key)
        print(success_message)
    except ParamValidationError as ex:
        message = ' '.join(['Unable to upload to s3.'
                            'This is likely due to a bad manifest file.'
                            'Check the file type and syntax.'])
        log_unsuccessful('upload', message, ex)
    except ClientError as ex:
        message = 'Unable to upload to s3.'
        log_unsuccessful('upload', message, ex)


def upload_manifest_to_s3(bucket: str, prefix: str, file: str, manifest: str) -> None:
    '''
    Upload the manifest to s3.
    '''
    prefix = prefix.rstrip('/') + '/'
    key = prefix + file
    print('\n### Uploading Manifest to s3\n')
    s3 = _connect_to_s3()
    _upload(s3, bucket, key, manifest)
