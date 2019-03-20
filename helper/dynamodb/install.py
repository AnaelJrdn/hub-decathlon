# Synchronization module for decathloncoach.com
# (c) 2019 Anael Jourdain, anael.jourdain.partner@decathlon.com
from tapiriik.settings import *
import json
import boto3

""" ***** GOOD TO KNOW *****
__________________________________________________
|PYTHON TYPE                     | DYNAMODB TYPE |
|________________________________|_______________|
|string	                         | String (S)    |
|integer	                     | Number (N)    |
|decimal.Decimal	             | Number (N)    |
|boto3.dynamodb.types.Binary	 | Binary (B)    |
|boolean	                     | Boolean (BOOL)|
|None	                         | Null (NULL)   |
|string set	                     | String Set (SS)
|integer set	                 | Number Set (NS)
|decimal.Decimal set	         | Number Set (NS)
|boto3.dynamodb.types.Binary set | Binary Set (BS)
|list	                         | List (L)      |
|dict	                         | Map (M)       |
-------------------------------------------------- 
"""

class SqsManager():

    AWS_ZONE = AWS_SQS_ZONE

    DYNAMO_TABLE_LIST = [
        {
            'table_name': 'Users',
            'AttributeDefinitions': [
                {'name': 'Created', 'type': 'String'},
                {'name': 'CreationIP', 'type': 'String'},
                {'name': 'Timezone', 'type': 'String'},
                {'name': 'Substitute', 'type': 'Boolean'},
                {'name': 'QueueGeneration', 'type': 'String'},
                {'name': 'SynchronizationHost', 'type': 'String'},
                {'name': 'SynchronizationStartTime', 'type': 'String'},
                {'name': 'SynchronizationProgress', 'type': 'String'},
                {'name': 'SynchronizationStep', 'type': 'String'},
                {'name': 'BlockingSyncErrorCount', 'type': 'Number'},
                {'name': 'ForcingExhaustiveSyncErrorCount', 'type': 'Number'},
                {'name': 'NonblockingSyncErrorCount', 'type': 'Number'},
                {'name': 'SyncExclusionCount', 'type': 'Number'},
                {'name': 'LastSynchronization', 'type': 'String'},
                {'name': 'LastSynchronizationVersion', 'type': 'Binary'},
                {'name': 'NextSynchronization', 'type': 'String'},
                {'name': 'QueuedAt', 'type': 'String'},
                {
                    'name': 'Config',
                    'type': 'Map',
                    'content': [
                        {'name': 'suppress_auto_sync', 'type': 'Boolean'},
                        {'name': 'sync_upload_delay', 'type': 'Number'},
                        {'name': 'sync_skip_before', 'type': 'String'},
                        {'name': 'historical_sync', 'type': 'Boolean'}
                    ]
                },
                {
                    'name': 'ConnectedServices',
                    'type': 'List',
                    'content': [
                        {
                            'name': None,
                            'type': 'Map',
                            'content': [
                                {'name': 'Service', 'type': 'String'},
                                {'name': 'ID', 'type': 'String'}
                            ]
                        }
                    ]
                }
            ],
            'KeySchema': [],
            'LocalSecondaryIndexes': [],
            'GlobalSecondaryIndexes': [],
            'BillingMode': '',
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 123,
                'WriteCapacityUnits': 123
            },
            'StreamSpecification': {
                'StreamEnabled': True, #false,
                'StreamViewType': '' #['NEW_IMAGE'|'OLD_IMAGE'|'NEW_AND_OLD_IMAGES'|'KEYS_ONLY']
            },
            'SSESpecification': {
                'Enabled': True, #false,
                'SSEType': '', #['AES256'|'KMS'],
                'KMSMasterKeyId': 'string'
            }

        },
        {
            'table_name': 'connections',
            'KeySchema': [{
                'AttributeName': '_id',
                'KeyType': 'HASH'
            }],
            'LocalSecondaryIndexes': [
                {
                    'IndexName': 'string',
                    'KeySchema': [
                        {
                            'AttributeName': 'Host',
                            'KeyType': 'RANGE' # Range for sort, hash for partition key
                        },
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL' | 'KEYS_ONLY' | 'INCLUDE',
                        'NonKeyAttributes': [
                            'string',
                        ]
                    }
                }
            ],
            'GlobalSecondaryIndexes': [],
        }
    ]
    _resource = None
    _table = None
    _table_name = None

    _batcher = None
    def __init__(self):
        print('--- INIT DYNAMODB INSTALL ---')



    def test_process(self):
        print('[Helper DynamoDB]--- Testing Dynamo manager')