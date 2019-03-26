from tapiriik.database import db, close_connections
from datetime import datetime, timedelta
# I resisted calling this file sync_watchdog_watchdog.py, but that's what it is.
# Normally a watchdog process runs on each server and detects hung/crashed
# synchronization tasks, returning them to the queue for another worker to pick
# up. Except, if the entire server goes down, the watchdog no longer runs and
# users get stuck. So, we need a watchdog for the watchdogs. A separate process
# reschedules users left stranded by a failed server/process.

from tapiriik.helper.dynamodb.manager import DynamoManager
from tapiriik.database.model.sync_workers import Sync_workers
from boto3.dynamodb.conditions import Attr


def process_global_watchdog():

    _dynamo_manager = DynamoManager()
    SERVER_WATCHDOG_TIMEOUT = timedelta(minutes=5)

    print("[Sync_global_watchdog]--- Global sync watchdog run at %s" % datetime.now())

    for host_record in db.sync_watchdogs.find():

        host = host_record['Host']
        host_id = host_record['_id']
        host_timestamp = host_record['Timestamp']

        if datetime.utcnow() - host_timestamp > SERVER_WATCHDOG_TIMEOUT:
            print("Releasing users held by %s (last check-in %s)" % (host, host_timestamp))
            db.users.update({"SynchronizationHost": host}, {"$unset": {"SynchronizationWorker": True}}, multi=True)

            clean_worker(_dynamo_manager, host)

            db.sync_watchdogs.remove({"_id": host_id})

    close_connections()


def clean_worker(_dynamo_manager, host):

    print("[Sync_global_watchdog]--- Processing sync_global_watchdog cleaner")
    _dynamo_manager.get_table('sync_workers')

    response = sync_worker_scanner(_dynamo_manager, host)
    for worker in response['Items']:
        worker_elem = Sync_workers(worker).get_item('dict')
        response = _dynamo_manager._table.delete_item(
            Key={
                'id': worker_elem['id'],
            }
        )

    while 'LastEvaluatedKey' in response:
        response = sync_worker_scanner(_dynamo_manager, host)
        for worker in response['Items']:
            worker_elem = Sync_workers(worker).get_item('dict')
            response = _dynamo_manager._table.delete_item(
                Key={
                    'id': worker_elem['id'],
                }
            )


def sync_worker_scanner(_dynamo_manager, host):
    _dynamo_manager.get_table('sync_workers')

    filter_expression = Attr('Host').eq(host)
    projection_expression = "id, Process, Host, HeartBeat, Startup, #Stte"
    expression_attribute_names = {"#Stte": "State"}

    print("[Sync_watchdog]--- Looking for sync_worker document with host : %s" % host)

    response = _dynamo_manager.scan(filter_expression, projection_expression, expression_attribute_names)
    return response

process_global_watchdog()