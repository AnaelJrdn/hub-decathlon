# Synchronization module for decathloncoach.com
# (c) 2019 Anael Jourdain, anael.jourdain.partner@decathlon.com
import json
import decimal
import boto3
import uuid
from boto3.dynamodb.conditions import Attr

class Users:

    _table_name = 'users'

    _create_conf = {
        'AttributeDefinitions': [{
            'AttributeName': 'id',
            'AttributeType': 'S'
        }],
        'KeySchema': [{
            'AttributeName': 'id',
            'KeyType': 'HASH'
        }],
        'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
    }

    id = None
    process = None
    host = None
    heartbeat = None
    index = None
    startup = None
    state = None
    version = None
    user = None


    # TODO: try to set only one value and see if other attributes are updated (or not, they shouldn't)
    def __init__(self, sync_worker_stats={}):
        if 'id' in sync_worker_stats:
            self.id = sync_worker_stats['id']
        else:
            self.id = str(uuid.uuid4().hex)

        if 'Process' in sync_worker_stats:
            self.process = sync_worker_stats['Process']
        if 'Host' in sync_worker_stats:
            self.host = sync_worker_stats['Host']

        if 'HeartBeat' in sync_worker_stats:
            self.heartbeat = sync_worker_stats['HeartBeat']
        if 'Index' in sync_worker_stats:
            self.index = sync_worker_stats['Index']

        if 'Startup' in sync_worker_stats:
            self.startup = sync_worker_stats['Startup']
        if 'State' in sync_worker_stats:
            self.state = sync_worker_stats['State']


        if 'Version' in sync_worker_stats:
            self.version = sync_worker_stats['Version']
        if 'User' in sync_worker_stats:
            self.user = sync_worker_stats['User']

    def __get_install_conf(self, format='json'):

        if format is 'json':
            return json.dumps(self.__create_conf)
        return self.__create_conf

    def get_item(self, format='json'):
        response = {
            'id': self.id,
            'Process': self.process,
            'Host': self.host,
            'HeartBeat': self.heartbeat,
            'Index': self.index,
            'Startup': self.startup,
            'State': self.state,
            'Version': self.version,
            'User': self.user,
        }
        if format is 'json':
            return json.dumps(response)

        if format is 'dict':
            return response
        return response

    def set_item(self, sync_worker_stats):

        if 'Process' in sync_worker_stats:
            self.process = sync_worker_stats['Process']
        if 'Host' in sync_worker_stats:
            self.host = sync_worker_stats['Host']

        if 'HeartBeat' in sync_worker_stats:
            self.heartbeat = sync_worker_stats['HeartBeat']
        if 'Index' in sync_worker_stats:
            self.index = sync_worker_stats['Index']

        if 'Startup' in sync_worker_stats:
            self.startup = sync_worker_stats['Startup']
        if 'State' in sync_worker_stats:
            self.state = sync_worker_stats['State']

        if 'Version' in sync_worker_stats:
            self.version = sync_worker_stats['Version']
        if 'User' in sync_worker_stats:
            self.user = sync_worker_stats['User']
