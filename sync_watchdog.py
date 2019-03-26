from tapiriik.database import db, close_connections
from tapiriik.sync import SyncStep
import os
import signal
import socket
from datetime import timedelta, datetime

from tapiriik.helper.dynamodb.manager import DynamoManager
from tapiriik.database.model.sync_workers import Sync_workers
from boto3.dynamodb.conditions import Attr


print("Sync watchdog run at %s" % datetime.now())

def watchdog_process():
    print("[Sync_watchdog]--- Processing sync_watchdog")

    host = socket.gethostname()
    _dynamo_manager = DynamoManager()

    response = sync_worker_scanner(_dynamo_manager, host)
    for worker in response['Items']:
        worker_elem = Sync_workers(worker).get_item('dict')

        # Does the process still exist?
        watchdog_subprocess(_dynamo_manager, worker_elem, host)

    while 'LastEvaluatedKey' in response:
        response = sync_worker_scanner(_dynamo_manager, host)

        for worker in response['Items']:
            worker_elem = Sync_workers(worker).get_item('dict')
            watchdog_subprocess(_dynamo_manager, worker_elem, host)

    # TODO : find then update ALL sync_watchdog document
    db.sync_watchdogs.update({"Host": host}, {"Host": host, "Timestamp": datetime.utcnow()}, upsert=True)
    # TODO : Connections not use anymore
    close_connections()


def watchdog_subprocess(_dynamo_manager, worker, host):

    alive = True

    try:
        os.kill(worker['Process'], 0)
        print("[Sync_watchdog]--- Killing Worker %s" % worker)
    except os.error:
        print("[Sync_watchdog]--- Worker %s is no longer alive" % worker['id'])
        alive = False

    timeout = timedelta(minutes=10)
    if worker['State'] == SyncStep.List:
        timeout = timedelta(minutes=45)

    if alive and worker['HeartBeat'] < datetime.utcnow() - timeout:
        print("[Sync_watchdog]--- Worker : %s timed out" % worker['id'])
        os.kill(worker['Process'], signal.SIGKILL)
        alive = False

    # Clear it from the database if it's not alive.
    if not alive:
        print("[Sync_watchdog]--- Worker is no longer alive")
        response = _dynamo_manager._table.delete_item(
            Key={
                'id': worker['id'],
            }
        )
        # Unlock users attached to it.
        # TODO : find then update userS documentS
        # db.users.update({"SynchronizationWorker": worker["Process"], "SynchronizationHost": host}, {"$unset":{"SynchronizationWorker": True}}, multi=True)


def sync_worker_scanner(_dynamo_manager, host):
    _dynamo_manager.get_table('sync_workers')

    filter_expression = Attr('Host').eq(host)
    projection_expression = "id, Process, Host, HeartBeat, Startup, #Stte"
    expression_attribute_names = {"#Stte": "State"}

    print("[Sync_watchdog]--- Looking for sync_worker document with host : %s" % socket.gethostname())

    response = _dynamo_manager.scan(filter_expression, projection_expression, expression_attribute_names)
    return response


watchdog_process()
