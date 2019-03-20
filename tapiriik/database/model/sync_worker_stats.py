# Synchronization module for decathloncoach.com
# (c) 2019 Anael Jourdain, anael.jourdain.partner@decathlon.com
import json
import decimal
import boto3
import uuid

class Sync_worker_stats():

    _table_name = 'sync_worker_stats'

    __create_conf = {
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
    worker = None
    host = None
    timestamp = None
    timetaken = None

    # TODO: try to set only one value and see if other attributes are updated (or not, they shouldn't)
    def __init__(self, sync_worker_stats):
        if 'id' in sync_worker_stats:
            self.id = sync_worker_stats['id']
        else:
            self.id = str(uuid.uuid4().hex)

        if 'Worker' in sync_worker_stats:
            self.worker = sync_worker_stats['Worker']
        if 'Host' in sync_worker_stats:
            self.host = sync_worker_stats['Host']
        if 'Timestamp' in sync_worker_stats:
            self.timestamp = sync_worker_stats['Timestamp']
        if 'Timetaken' in sync_worker_stats:
            self.timetaken = sync_worker_stats['Timetaken']

    def get_item(self, format='json'):
        response = {
            'id': self.id,
            'Worker': self.worker,
            'Host': self.host,
            'Timestamp': self.timestamp,
            'Timetaken': self.timetaken,
        }
        if format is 'json':
            return json.dumps(response)

        if format is 'dict':
            return response
        return response

    def set_item(self, sync_worker_stats):
        if 'worker' in sync_worker_stats:
            self.worker = sync_worker_stats['worker']
        if 'host' in sync_worker_stats:
            self.host = sync_worker_stats['host']
        if 'timestamp' in sync_worker_stats:
            self.timestamp = sync_worker_stats['timestamp']
        if 'timetaken' in sync_worker_stats:
            self.timetaken = sync_worker_stats['timetaken']

